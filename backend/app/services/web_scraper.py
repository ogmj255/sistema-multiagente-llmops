from datetime import UTC, datetime

import httpx
from bs4 import BeautifulSoup
from bs4.element import Tag
from playwright.sync_api import (
    TimeoutError as PlaywrightTimeoutError,
)
from playwright.sync_api import (
    sync_playwright,
)

from app.schemas.contract import (
    ContractSection,
    ExtractedContract,
    ExtractionRequest,
    SourceArea,
)

USER_AGENT = "Sistema-Multiagente-LLMOps/0.1 (proyecto-academico)"

HEADING_TAGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})
CONTENT_TAGS = frozenset({"p", "li", "blockquote", "dt", "dd", "pre"})
GENERIC_TAGS = frozenset({"div", "section"})
INTERACTIVE_TAGS = frozenset({"button", "form", "dialog", "select", "input"})
TABLE_TAGS = frozenset(
    {"table", "thead", "tbody", "tfoot", "tr", "td", "th"}
)
TABLE_CELL_TAGS = frozenset({"td", "th"})
LINK_TEXT_RATIO_THRESHOLD = 0.5


def normalize_html_text(text: str) -> str:
    """Normaliza espacios del texto extraído del HTML."""
    return " ".join(text.replace("\u00a0", " ").split())

def get_usable_content_length(
    contract: ExtractedContract,
) -> int:
    """Calcula el contenido extraído fuera de áreas de ruido."""

    return sum(
        len(section.content.strip())
        for section in contract.sections
        if section.source_area in {"content", "body"}
    )

def has_sufficient_contract_content(
    contract: ExtractedContract,
) -> bool:
    """Comprueba si existe contenido contractual utilizable."""

    return get_usable_content_length(contract) > 0


def is_heading(element: Tag) -> bool:
    """Comprueba si un elemento es un encabezado HTML estándar."""
    return element.name in HEADING_TAGS


def get_heading_level(element: Tag) -> int:
    """Obtiene el nivel de un encabezado h1-h6."""
    return int(element.name[1])


def contains_only_links(element: Tag) -> bool:
    """Comprueba si todo el texto del elemento procede de enlaces."""
    links = element.find_all("a")
    if not links:
        return False

    element_text = normalize_html_text(element.get_text(" ", strip=True))
    links_text = normalize_html_text(
        " ".join(link.get_text(" ", strip=True) for link in links)
    )
    return element_text == links_text

def belongs_to_link_collection(element: Tag) -> bool:
    """Detecta ?ndices o men?s mediante su proporci?n de enlaces."""
    current: Tag | None = element

    while isinstance(current, Tag):
        if current.name in {"main", "article", "body", "html"}:
            break

        links = current.find_all("a")

        if len(links) >= 2:
            total_text = normalize_html_text(
                current.get_text(" ", strip=True)
            ).replace(" ", "")
            links_text = normalize_html_text(
                " ".join(
                    link.get_text(" ", strip=True)
                    for link in links
                )
            ).replace(" ", "")

            if (
                total_text
                and len(links_text) / len(total_text)
                >= LINK_TEXT_RATIO_THRESHOLD
            ):
                return True

        parent = current.parent
        current = parent if isinstance(parent, Tag) else None

    return False

def identify_source_area(element: Tag) -> SourceArea:
    """Identifica el área estructural de un elemento HTML."""

    if element.find_parent("nav") is not None:
        return "navigation"
    if element.find_parent("aside") is not None:
        return "aside"
    if element.find_parent("header") is not None:
        return "header"
    if element.find_parent("footer") is not None:
        return "footer"

    if (
        element.name in INTERACTIVE_TAGS
        or element.find_parent(list(INTERACTIVE_TAGS)) is not None
    ):
        return "interactive"

    link_count = len(element.find_all("a"))

    if is_heading(element) and belongs_to_link_collection(element):
        return "navigation"

    if contains_only_links(element) and (
        link_count >= 2 or belongs_to_link_collection(element)
    ):
        return "navigation"

    if element.find_parent(["main", "article"]) is not None:
        return "content"

    return "body"


def is_inside_table_cell(element: Tag) -> bool:
    """Evita procesar contenido interno de celdas por separado.

    El contenido de <td>/<th> se extrae a nivel de fila (ver
    build_table_row_text), no como bloques independientes; de lo
    contrario un párrafo dentro de una celda se duplicaría.
    """
    return element.find_parent(list(TABLE_CELL_TAGS)) is not None


def is_nested_content_element(element: Tag) -> bool:
    """Evita repetir bloques dentro de otro bloque textual."""
    return element.find_parent(list(CONTENT_TAGS)) is not None


def is_meaningful_table_row(element: Tag) -> bool:
    """Determina si una fila de tabla debe convertirse en cláusula.

    Una fila compuesta únicamente por celdas <th> es una cabecera
    estructural (nombres de columna) y no aporta contenido jurídico
    por sí sola.
    """
    if element.name != "tr":
        return False

    cells = element.find_all(list(TABLE_CELL_TAGS), recursive=False)
    if not cells:
        return False

    return any(cell.name == "td" for cell in cells)


def build_table_row_text(row: Tag) -> str:
    """Construye el texto de una fila conservando el orden de sus celdas."""
    cells = row.find_all(list(TABLE_CELL_TAGS), recursive=False)
    cell_texts = [
        normalize_html_text(cell.get_text(" ", strip=True)) for cell in cells
    ]
    return " | ".join(text for text in cell_texts if text)



def is_semantic_candidate(element: Tag) -> bool:
    """Selecciona elementos HTML sem?nticos est?ndar."""
    if is_inside_table_cell(element):
        return False

    if (
        element.name in CONTENT_TAGS
        and is_nested_content_element(element)
    ):
        return False

    return (
        is_heading(element)
        or element.name in CONTENT_TAGS
        or is_meaningful_table_row(element)
    )


def is_generic_text_container(element: Tag) -> bool:
    """Selecciona contenedores gen?ricos aislados con texto visible."""
    if element.name not in GENERIC_TAGS:
        return False

    structural_tags = HEADING_TAGS | CONTENT_TAGS | TABLE_TAGS

    if element.find_parent(list(structural_tags)) is not None:
        return False
    if element.find_parent(list(INTERACTIVE_TAGS)) is not None:
        return False
    if element.find(list(structural_tags)) is not None:
        return False
    if element.find(list(INTERACTIVE_TAGS)) is not None:
        return False

    for descendant in element.find_all(list(GENERIC_TAGS)):
        descendant_text = normalize_html_text(
            descendant.get_text(" ", strip=True)
        )
        if descendant_text:
            return False

    return bool(normalize_html_text(element.get_text(" ", strip=True)))


def is_text_candidate(element: Tag) -> bool:
    """Selecciona bloques semanticos o genericos aislados."""
    return (
        is_semantic_candidate(element)
        or is_generic_text_container(element)
    )

def remove_non_visible_elements(soup: BeautifulSoup) -> None:
    """Elimina elementos técnicos y ocultos."""
    for element in soup.find_all(["script", "style", "noscript", "template"]):
        element.decompose()

    hidden_elements: list[Tag] = []
    for element in soup.find_all(True):
        style = str(element.get("style", "")).lower().replace(" ", "")
        if (
            element.has_attr("hidden")
            or str(element.get("aria-hidden", "")).lower() == "true"
            or "display:none" in style
            or "visibility:hidden" in style
        ):
            hidden_elements.append(element)

    for element in reversed(hidden_elements):
        element.decompose()


def build_section(
    element: Tag,
    order: int,
    heading: str | None,
    heading_level: int | None,
    text: str,
) -> ContractSection:
    links = element.find_all("a")
    return ContractSection(
        order=order,
        heading=heading,
        heading_level=heading_level,
        content=text,
        html_tag=element.name,
        source_area=identify_source_area(element),
        is_link_only=contains_only_links(element),
        link_count=len(links),
    )


def extract_sections(
    candidates: list[Tag],
    content_heading_levels: frozenset[int],
) -> list[ContractSection]:
    """Recorre los elementos candidatos y construye las secciones."""
    sections: list[ContractSection] = []
    headings_by_area: dict[SourceArea, tuple[str, int]] = {}
    last_content_heading: tuple[str, int] | None = None

    for element in candidates:
        is_row = element.name == "tr"
        text = (
            build_table_row_text(element)
            if is_row
            else normalize_html_text(element.get_text(" ", strip=True))
        )
        if not text:
            continue

        source_area = identify_source_area(element)

        is_content_heading = (
            is_heading(element)
            and get_heading_level(element)
            in content_heading_levels
        )

        if (
            not is_row
            and is_heading(element)
            and not is_content_heading
        ):
            heading_data = (text, get_heading_level(element))
            headings_by_area[source_area] = heading_data
            if source_area in {"content", "body"}:
                last_content_heading = heading_data
            continue

        heading_data = headings_by_area.get(source_area)
        if heading_data is None and source_area in {"content", "body"}:
            heading_data = last_content_heading

        heading = heading_data[0] if heading_data else None
        heading_level = heading_data[1] if heading_data else None

        sections.append(
            build_section(
                element, len(sections) + 1, heading, heading_level, text
            )
        )
    return sections

def detect_content_heading_levels(
    candidates: list[Tag],
) -> frozenset[int]:
    """Detecta niveles de encabezado utilizados como contenido."""

    heading_lengths: dict[int, int] = {}
    content_length = 0

    for element in candidates:
        if identify_source_area(element) not in {
            "content",
            "body",
        }:
            continue

        text = normalize_html_text(
            element.get_text(" ", strip=True)
        )
        if not text:
            continue

        if is_heading(element):
            level = get_heading_level(element)
            heading_lengths[level] = (
                heading_lengths.get(level, 0)
                + len(text)
            )
        else:
            content_length += len(text)

    if not heading_lengths:
        return frozenset()

    shallowest_level = min(heading_lengths)

    return frozenset(
        level
        for level, text_length in heading_lengths.items()
        if (
            level > shallowest_level
            and text_length > content_length
        )
    )

def parse_static_html(
    html: str,
) -> tuple[str, str, list[ContractSection], str]:
    """Obtiene el contenido visible y su estructura desde un HTML."""
    soup = BeautifulSoup(html, "html.parser")
    remove_non_visible_elements(soup)

    title = (
        soup.title.get_text(" ", strip=True)
        if soup.title
        else "Sin titulo"
    )

    language = "unknown"
    if soup.html and soup.html.get("lang"):
        language = str(soup.html.get("lang")).split("-")[0]

    document_body = soup.body
    if document_body is None:
        raise ValueError(
            "No se encontro contenido HTML para procesar."
        )

    candidates = document_body.find_all(
        is_text_candidate
    )
    content_heading_levels = detect_content_heading_levels(
        candidates
    )
    sections = extract_sections(
        candidates,
        content_heading_levels,
    )

    if not sections:
        raise ValueError(
            "No se encontraron bloques de texto en la pagina."
        )

    full_text = "\n\n".join(
        section.content for section in sections
    )
    return title, language, sections, full_text

def extract_static_contract(request: ExtractionRequest) -> ExtractedContract:
    """Descarga un contrato publicado como HTML estático."""
    response = httpx.get(
        str(request.url),
        follow_redirects=True,
        timeout=20.0,
        headers={"User-Agent": USER_AGENT},
    )
    response.raise_for_status()

    content_type = response.headers.get("content-type", "")
    if "text/html" not in content_type:
        raise ValueError("La dirección no contiene un documento HTML.")

    title, language, sections, full_text = parse_static_html(response.text)
    platform = request.platform or request.url.host or "unknown"

    return ExtractedContract(
        source_url=request.url,
        platform=platform,
        title=title,
        retrieved_at=datetime.now(UTC),
        extraction_method="beautiful_soup",
        language=language,
        sections=sections,
        full_text=full_text,
    )


def extract_dynamic_contract(
    request: ExtractionRequest,
) -> ExtractedContract:
    """Descarga un contrato publicado en una página dinámica."""

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()

        page.goto(
            str(request.url),
            wait_until="domcontentloaded",
            timeout=30_000,
        )

        try:
            page.wait_for_load_state(
                "networkidle",
                timeout=10_000,
            )
        except PlaywrightTimeoutError:
            pass

        html = page.content()
        browser.close()

    title, language, sections, full_text = parse_static_html(html)
    platform = request.platform or request.url.host or "unknown"

    return ExtractedContract(
        source_url=request.url,
        platform=platform,
        title=title,
        retrieved_at=datetime.now(UTC),
        extraction_method="playwright",
        language=language,
        sections=sections,
        full_text=full_text,
    )