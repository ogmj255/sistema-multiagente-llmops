import re
from datetime import UTC, datetime

import httpx
from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag
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

# Identificador enviado en las solicitudes HTTP del Web Scraper.
USER_AGENT = "Sistema-Multiagente-LLMOps/0.1 (proyecto-academico)"


# Etiquetas HTML utilizadas para clasificar y extraer contenido.
HEADING_TAGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})
CONTENT_TAGS = frozenset({"p", "li", "blockquote", "dt", "dd", "pre"})
GENERIC_TAGS = frozenset({"div", "section"})
INTERACTIVE_TAGS = frozenset({"button", "form", "dialog", "select", "input"})
TABLE_TAGS = frozenset({"table", "thead", "tbody", "tfoot", "tr", "td", "th"})
TABLE_CELL_TAGS = frozenset({"td", "th"})


# Proporción mínima de texto compuesto por enlaces para considerar navegación.
LINK_TEXT_RATIO_THRESHOLD = 0.5
MIN_BODY_USABLE_CHARACTERS = 80

# Señales estructurales frecuentes utilizadas en class, id o role.
ATTRIBUTE_AREA_HINTS: tuple[
    tuple[SourceArea, frozenset[str]],
    ...,
] = (
    (
        "navigation",
        frozenset(
            {
                "nav",
                "navigation",
                "menu",
                "breadcrumb",
                "breadcrumbs",
            }
        ),
    ),
    (
        "aside",
        frozenset(
            {
                "aside",
                "sidebar",
                "related",
            }
        ),
    ),
    (
        "header",
        frozenset(
            {
                "header",
            }
        ),
    ),
    (
        "footer",
        frozenset(
            {
                "footer",
            }
        ),
    ),
    (
        "interactive",
        frozenset(
            {
                "cookie",
                "cookies",
                "consent",
                "newsletter",
                "subscribe",
                "subscription",
                "popup",
                "modal",
            }
        ),
    ),
)


def normalize_html_text(text: str) -> str:
    """Normaliza espacios del texto extraído del HTML."""

    # Elimina espacios repetidos y reemplaza espacios HTML no separables.
    return " ".join(text.replace("\u00a0", " ").split())


def get_usable_content_length(
    contract: ExtractedContract,
) -> int:
    """Calcula el contenido extraído fuera de áreas de ruido."""

    # Suma únicamente el texto perteneciente al contenido principal o body.
    return sum(
        len(section.content.strip())
        for section in contract.sections
        if section.source_area in {"content", "body"}
    )


def get_generic_container_text(
    element: Tag,
) -> str:
    """Obtiene el texto propio de un contenedor genérico."""

    structural_area_tags = frozenset(
        {"nav", "header", "footer", "aside"}
    )

    boundary_tags = (
        HEADING_TAGS
        | CONTENT_TAGS
        | TABLE_TAGS
        | GENERIC_TAGS
        | INTERACTIVE_TAGS
        | structural_area_tags
    )

    parts: list[str] = []

    for child in element.children:
        if isinstance(child, NavigableString):
            parts.append(str(child))
            continue

        if not isinstance(child, Tag):
            continue

        # Ignora bloques estructurados y wrappers que los contengan.
        if (
            child.name in boundary_tags
            or child.find(list(boundary_tags)) is not None
        ):
            continue

        # Conserva únicamente contenido inline sin estructura interna.
        parts.append(
            child.get_text(
                " ",
                strip=True,
            )
        )

    return normalize_html_text(" ".join(parts))


def has_sufficient_contract_content(
    contract: ExtractedContract,
) -> bool:
    """Comprueba si existe contenido contractual utilizable."""

    content_length = sum(
        len(section.content.strip())
        for section in contract.sections
        if section.source_area == "content"
    )

    # El contenido ubicado explícitamente en main/article
    # se considera una señal estructural suficiente.
    if content_length > 0:
        return True

    body_length = sum(
        len(section.content.strip())
        for section in contract.sections
        if section.source_area == "body"
    )

    # El body funciona como respaldo y requiere más contenido
    # para evitar aceptar fragmentos aislados.
    return body_length >= MIN_BODY_USABLE_CHARACTERS


def is_heading(element: Tag) -> bool:
    """Comprueba si un elemento es un encabezado HTML estándar."""

    # Verifica si la etiqueta corresponde a h1-h6.
    return element.name in HEADING_TAGS


def get_heading_level(element: Tag) -> int:
    """Obtiene el nivel de un encabezado h1-h6."""

    # Convierte h1-h6 en su nivel numérico correspondiente.
    return int(element.name[1])


def contains_only_links(element: Tag) -> bool:
    """Comprueba si todo el texto del elemento procede de enlaces."""

    # Obtiene todos los enlaces contenidos dentro del elemento.
    links = element.find_all("a")

    if not links:
        return False

    # Compara el texto total del elemento con el texto de sus enlaces.
    element_text = normalize_html_text(element.get_text(" ", strip=True))
    links_text = normalize_html_text(
        " ".join(link.get_text(" ", strip=True) for link in links)
    )

    return element_text == links_text


def is_fully_emphasized(
    element: Tag,
) -> bool:
    """Comprueba si todo el texto visible está resaltado."""

    text_nodes = [
        node
        for node in element.descendants
        if (isinstance(node, NavigableString) and normalize_html_text(str(node)))
    ]

    if not text_nodes:
        return False

    for node in text_nodes:
        parent = node.parent

        if not isinstance(parent, Tag):
            return False

        if (
            parent.name not in {"strong", "b"}
            and parent.find_parent(["strong", "b"]) is None
        ):
            return False

    return True


def belongs_to_link_collection(element: Tag) -> bool:
    """Detecta índices o menús mediante su proporción de enlaces."""

    # Recorre el elemento y sus contenedores padres.
    current: Tag | None = element

    while isinstance(current, Tag):
        # Detiene la búsqueda al alcanzar el contenido principal.
        if current.name in {"main", "article", "body", "html"}:
            break

        links = current.find_all("a")

        # Analiza contenedores que poseen al menos dos enlaces.
        if len(links) >= 2:
            total_text = normalize_html_text(current.get_text(" ", strip=True)).replace(
                " ", ""
            )

            links_text = normalize_html_text(
                " ".join(link.get_text(" ", strip=True) for link in links)
            ).replace(" ", "")

            # Considera navegación si los enlaces representan
            # una proporción importante del texto del contenedor.
            if (
                total_text
                and len(links_text) / len(total_text) >= LINK_TEXT_RATIO_THRESHOLD
            ):
                return True

        # Continúa evaluando el elemento padre.
        parent = current.parent
        current = parent if isinstance(parent, Tag) else None

    return False


def identify_attribute_area(
    element: Tag,
) -> SourceArea | None:
    """Detecta áreas estructurales mediante class, id y role."""

    current: Tag | None = element

    while isinstance(current, Tag):
        classes = current.get("class", [])
        if isinstance(classes, str):
            classes = [classes]

        attribute_text = " ".join(
            [
                str(current.get("id", "")),
                str(current.get("role", "")),
                *[str(value) for value in classes],
            ]
        ).lower()

        tokens = frozenset(
            re.findall(
                r"[a-z0-9]+",
                attribute_text,
            )
        )

        for source_area, hints in ATTRIBUTE_AREA_HINTS:
            if not tokens & hints:
                continue

            # Un "header" definido por clases dentro del contenido principal
            # suele representar un encabezado de sección, no la cabecera del sitio.
            if (
                source_area == "header"
                and current.find_parent(["main", "article"]) is not None
            ):
                continue

            return source_area

        if current.name in {"body", "html"}:
            break

        parent = current.parent
        current = parent if isinstance(parent, Tag) else None

    return None


def identify_source_area(element: Tag) -> SourceArea:
    """Identifica el área estructural de un elemento HTML."""

    # Clasifica elementos ubicados dentro de áreas HTML conocidas.
    if element.find_parent("nav") is not None:
        return "navigation"

    if element.find_parent("aside") is not None:
        return "aside"

    if element.find_parent("header") is not None:
        return "header"

    if element.find_parent("footer") is not None:
        return "footer"

    attribute_area = identify_attribute_area(element)
    if attribute_area is not None:
        return attribute_area

    # Clasifica elementos interactivos o contenidos dentro de ellos.
    if (
        element.name in INTERACTIVE_TAGS
        or element.find_parent(list(INTERACTIVE_TAGS)) is not None
    ):
        return "interactive"

    # Cuenta los enlaces internos del bloque.
    link_count = len(element.find_all("a"))

    # Detecta encabezados que forman parte de menús o índices.
    if is_heading(element) and belongs_to_link_collection(element):
        return "navigation"

    # Detecta bloques compuestos principalmente por enlaces.
    if contains_only_links(element) and (
        link_count >= 2 or belongs_to_link_collection(element)
    ):
        return "navigation"

    # Considera contenido principal lo ubicado dentro de main o article.
    if element.find_parent(["main", "article"]) is not None:
        return "content"

    # El resto del contenido visible se considera parte del body.
    return "body"


def is_inside_table_cell(element: Tag) -> bool:
    """Evita procesar contenido interno de celdas por separado.

    El contenido de <td>/<th> se extrae a nivel de fila (ver
    build_table_row_text), no como bloques independientes; de lo
    contrario un párrafo dentro de una celda se duplicaría.
    """

    # Comprueba si el elemento está dentro de una celda de tabla.
    return element.find_parent(list(TABLE_CELL_TAGS)) is not None


def is_nested_content_element(element: Tag) -> bool:
    """Evita repetir bloques dentro de otro bloque textual."""

    # Detecta contenido textual anidado dentro de otro bloque textual.
    return element.find_parent(list(CONTENT_TAGS)) is not None


def is_meaningful_table_row(element: Tag) -> bool:
    """Determina si una fila de tabla debe convertirse en cláusula.

    Una fila compuesta únicamente por celdas <th> es una cabecera
    estructural (nombres de columna) y no aporta contenido jurídico
    por sí sola.
    """

    # Solo procesa elementos correspondientes a filas de tabla.
    if element.name != "tr":
        return False

    # Obtiene las celdas directas de la fila.
    cells = element.find_all(
        list(TABLE_CELL_TAGS),
        recursive=False,
    )

    if not cells:
        return False

    # Considera relevante una fila que contenga al menos una celda <td>.
    return any(cell.name == "td" for cell in cells)


def build_table_row_text(row: Tag) -> str:
    """Construye el texto de una fila conservando el orden de sus celdas."""

    # Obtiene las celdas directas de la fila.
    cells = row.find_all(
        list(TABLE_CELL_TAGS),
        recursive=False,
    )

    # Normaliza individualmente el contenido de cada celda.
    cell_texts = [normalize_html_text(cell.get_text(" ", strip=True)) for cell in cells]

    # Une las celdas manteniendo su orden original.
    return " | ".join(text for text in cell_texts if text)


def is_semantic_candidate(element: Tag) -> bool:
    """Selecciona elementos HTML semánticos estándar."""

    # Evita duplicar contenido que ya será procesado a nivel de fila.
    if is_inside_table_cell(element):
        return False

    # Evita procesar bloques textuales anidados varias veces.
    if element.name in CONTENT_TAGS and is_nested_content_element(element):
        return False

    # Acepta encabezados, bloques textuales y filas relevantes.
    return (
        is_heading(element)
        or element.name in CONTENT_TAGS
        or is_meaningful_table_row(element)
    )


def is_generic_text_container(element: Tag) -> bool:
    """Selecciona contenedores genéricos con texto propio."""

    if element.name not in GENERIC_TAGS:
        return False

    structural_tags = HEADING_TAGS | CONTENT_TAGS | TABLE_TAGS

    if element.find_parent(list(structural_tags)) is not None:
        return False

    if element.find_parent(list(INTERACTIVE_TAGS)) is not None:
        return False

    # Evita convertir menús o índices de enlaces en contenido contractual.
    if belongs_to_link_collection(element):
        return False

    return bool(get_generic_container_text(element))


def is_text_candidate(element: Tag) -> bool:
    """Selecciona bloques semánticos o genéricos aislados."""

    # Acepta elementos semánticos o contenedores genéricos válidos.
    return is_semantic_candidate(element) or is_generic_text_container(element)


def remove_non_visible_elements(
    soup: BeautifulSoup,
) -> None:
    """Elimina elementos técnicos y ocultos."""

    # Elimina elementos que no representan contenido visible.
    for element in soup.find_all(
        [
            "script",
            "style",
            "noscript",
            "template",
        ]
    ):
        element.decompose()

    hidden_elements: list[Tag] = []

    # Busca elementos ocultos mediante atributos o estilos HTML.
    for element in soup.find_all(True):
        style = str(element.get("style", "")).lower().replace(" ", "")

        if (
            element.has_attr("hidden")
            or str(element.get("aria-hidden", "")).lower() == "true"
            or "display:none" in style
            or "visibility:hidden" in style
        ):
            hidden_elements.append(element)

    # Elimina los elementos ocultos encontrados.
    for element in reversed(hidden_elements):
        element.decompose()


def build_section(
    element: Tag,
    order: int,
    heading: str | None,
    heading_level: int | None,
    text: str,
) -> ContractSection:

    # Obtiene los enlaces presentes dentro del bloque.
    links = element.find_all("a")

    # Construye la representación estructurada del bloque extraído.
    return ContractSection(
        order=order,
        heading=heading,
        heading_level=heading_level,
        content=text,
        html_tag=element.name,
        is_fully_emphasized=is_fully_emphasized(element),
        source_area=identify_source_area(element),
        is_link_only=contains_only_links(element),
        link_count=len(links),
    )


def extract_sections(
    candidates: list[Tag],
    content_heading_levels: frozenset[int],
) -> list[ContractSection]:
    """Recorre los elementos candidatos y construye las secciones."""

    # Almacena las secciones extraídas en su orden original.
    sections: list[ContractSection] = []

    # Conserva el último encabezado identificado para cada área.
    headings_by_area: dict[
        SourceArea,
        tuple[str, int],
    ] = {}

    # Conserva el último encabezado asociado al contenido principal.
    last_content_heading: tuple[str, int] | None = None

    for element in candidates:
        # Identifica si el candidato corresponde a una fila de tabla.
        is_row = element.name == "tr"

        # Obtiene el texto según el tipo de elemento.
        if is_row:
            text = build_table_row_text(element)
        elif element.name in GENERIC_TAGS:
            text = get_generic_container_text(element)
        else:
            text = normalize_html_text(element.get_text(" ", strip=True))

        # Ignora elementos sin contenido textual.
        if not text:
            continue

        # Determina de qué área de la página proviene el elemento.
        source_area = identify_source_area(element)

        # Detecta encabezados que realmente están siendo usados como contenido.
        is_content_heading = (
            is_heading(element) and get_heading_level(element) in content_heading_levels
        )

        # Los encabezados normales se guardan como contexto
        # para las secciones posteriores.
        if not is_row and is_heading(element) and not is_content_heading:
            heading_data = (
                text,
                get_heading_level(element),
            )

            headings_by_area[source_area] = heading_data

            if source_area in {"content", "body"}:
                last_content_heading = heading_data

            continue

        # Busca el encabezado correspondiente al área actual.
        heading_data = headings_by_area.get(source_area)

        # Usa el último encabezado principal como respaldo.
        if heading_data is None and source_area in {"content", "body"}:
            heading_data = last_content_heading

        heading = heading_data[0] if heading_data else None

        heading_level = heading_data[1] if heading_data else None

        # Convierte el elemento HTML en una sección contractual.
        sections.append(
            build_section(
                element,
                len(sections) + 1,
                heading,
                heading_level,
                text,
            )
        )

    return sections


def detect_content_heading_levels(
    candidates: list[Tag],
) -> frozenset[int]:
    """Detecta niveles de encabezado utilizados como contenido."""

    # Acumula la cantidad de texto encontrada por cada nivel h1-h6.
    heading_lengths: dict[int, int] = {}

    # Acumula la longitud del contenido que no corresponde a encabezados.
    content_length = 0

    for element in candidates:
        # Solo evalúa contenido principal o contenido general del body.
        if identify_source_area(element) not in {
            "content",
            "body",
        }:
            continue

        text = normalize_html_text(element.get_text(" ", strip=True))

        if not text:
            continue

        # Acumula texto según el nivel del encabezado.
        if is_heading(element):
            level = get_heading_level(element)

            heading_lengths[level] = heading_lengths.get(level, 0) + len(text)

        else:
            content_length += len(text)

    # Si no existen encabezados, no hay niveles que reclasificar.
    if not heading_lengths:
        return frozenset()

    # Obtiene el nivel de encabezado más superficial encontrado.
    shallowest_level = min(heading_lengths)

    # Detecta niveles profundos cuyo texto se comporta
    # más como contenido que como encabezado.
    return frozenset(
        level
        for level, text_length in heading_lengths.items()
        if (level > shallowest_level and text_length > content_length)
    )


def parse_static_html(
    html: str,
) -> tuple[
    str,
    str,
    list[ContractSection],
    str,
]:
    """Obtiene el contenido visible y su estructura desde un HTML."""

    # Construye el árbol HTML.
    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    # Elimina contenido técnico u oculto antes de extraer texto.
    remove_non_visible_elements(soup)

    # Obtiene el título de la página.
    title = soup.title.get_text(" ", strip=True) if soup.title else "Sin titulo"

    # Obtiene el idioma declarado en la etiqueta <html>.
    language = "unknown"

    if soup.html and soup.html.get("lang"):
        language = str(soup.html.get("lang")).split("-")[0]

    # Obtiene el contenido principal del documento HTML.
    document_body = soup.body

    if document_body is None:
        raise ValueError("No se encontro contenido HTML para procesar.")

    # Selecciona los elementos que pueden contener texto relevante.
    candidates = document_body.find_all(is_text_candidate)

    # Identifica niveles de encabezado utilizados realmente como contenido.
    content_heading_levels = detect_content_heading_levels(candidates)

    # Convierte los candidatos HTML en secciones estructuradas.
    sections = extract_sections(
        candidates,
        content_heading_levels,
    )

    # Rechaza documentos donde no se pudo extraer ningún bloque textual.
    if not sections:
        raise ValueError("No se encontraron bloques de texto en la pagina.")

    # Construye una representación textual completa del documento.
    full_text = "\n\n".join(
    section.content
    for section in sections
    if section.source_area in {"content", "body"}
)

    return (
        title,
        language,
        sections,
        full_text,
    )


def extract_static_contract(
    request: ExtractionRequest,
) -> ExtractedContract:
    """Descarga un contrato publicado como HTML estático."""

    # Realiza la solicitud HTTP directamente a la URL recibida.
    response = httpx.get(
        str(request.url),
        follow_redirects=True,
        timeout=20.0,
        headers={
            "User-Agent": USER_AGENT,
        },
    )

    # Genera una excepción cuando la respuesta HTTP indica un error.
    response.raise_for_status()

    # Verifica que la respuesta corresponda a contenido HTML.
    content_type = response.headers.get(
        "content-type",
        "",
    )

    if "text/html" not in content_type:
        raise ValueError("La dirección no contiene un documento HTML.")

    # Procesa el HTML obtenido y extrae su estructura textual.
    (
        title,
        language,
        sections,
        full_text,
    ) = parse_static_html(response.text)

    # Usa la plataforma indicada o, en su defecto, el dominio de la URL.
    platform = request.platform or request.url.host or "unknown"

    # Construye el contrato extraído mediante BeautifulSoup.
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

    # Inicia Playwright para cargar la página en un navegador real.
    with sync_playwright() as playwright:
        # Inicia una instancia de Chromium.
        browser = playwright.chromium.launch()

        try:
            # Crea una nueva página del navegador.
            page = browser.new_page()

            # Navega hacia la URL y espera que el DOM inicial esté cargado.
            navigation_response = page.goto(
                str(request.url),
                wait_until="domcontentloaded",
                timeout=30_000,
            )

            # Comprueba que Playwright haya recibido una respuesta HTTP.
            if navigation_response is None:
                raise ValueError("La navegación no devolvió una respuesta HTTP.")

            # Rechaza respuestas HTTP que indiquen error.
            if not navigation_response.ok:
                raise ValueError(
                    f"La página devolvió un estado HTTP {navigation_response.status}."
                )

            try:
                # Espera que la actividad de red disminuya
                # para permitir la carga de contenido dinámico.
                page.wait_for_load_state(
                    "networkidle",
                    timeout=10_000,
                )

            # Si networkidle tarda demasiado, continúa con el HTML disponible.
            except PlaywrightTimeoutError:
                pass

            # Elimina elementos que el navegador mantiene en el DOM,
            # pero que no forman parte del contenido visible de la página.
            page.evaluate(
                """
                () => {
                    const elements = Array.from(
                        document.body.querySelectorAll("*")
                    );

                    for (const element of elements.reverse()) {
                        const style = window.getComputedStyle(element);

                        if (
                            style.display === "none"
                            || style.visibility === "hidden"
                            || style.visibility === "collapse"
                        ) {
                            element.remove();
                        }
                    }
                }
                """
            )

            # Obtiene únicamente el HTML renderizado restante.
            html = page.content()
        finally:
            # Cierra el navegador incluso cuando ocurre una excepción.
            browser.close()

    # Procesa el HTML renderizado con la misma lógica del método estático.
    (
        title,
        language,
        sections,
        full_text,
    ) = parse_static_html(html)

    # Usa la plataforma indicada o, en su defecto, el dominio de la URL.
    platform = request.platform or request.url.host or "unknown"

    # Construye el contrato indicando que fue extraído mediante Playwright.
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
