import unicodedata

from bs4 import BeautifulSoup
from bs4.element import Comment, NavigableString, Tag

from app.schemas.contract import ContractSection
from app.schemas.preprocessing import RemovedBlock

SPECIAL_SPACE_TRANSLATION = str.maketrans(
    {
        "\u00a0": " ",
        "\u2007": " ",
        "\u202f": " ",
    }
)

HEADING_TAGS = frozenset(
    {"h1", "h2", "h3", "h4", "h5", "h6"}
)

CONTENT_TAGS = frozenset(
    {
        "p",
        "li",
        "blockquote",
        "dt",
        "dd",
        "pre",
    }
)

GENERIC_TAGS = frozenset(
    {
        "div",
        "section",
    }
)

TABLE_CELL_TAGS = frozenset(
    {
        "td",
        "th",
    }
)

NOISE_TAGS = frozenset(
    {
        "script",
        "style",
        "noscript",
        "template",
        "nav",
        "footer",
        "aside",
        "form",
        "dialog",
        "select",
        "input",
        "button",
    }
)

NOISE_ROLES = frozenset(
    {
        "navigation",
        "contentinfo",
        "complementary",
        "dialog",
    }
)


def normalize_text(text: str) -> str:
    """Normaliza Unicode y espacios sin alterar el significado."""

    normalized = unicodedata.normalize(
        "NFC",
        text,
    )

    normalized = normalized.replace(
        "\ufeff",
        "",
    )

    normalized = normalized.translate(
        SPECIAL_SPACE_TRANSLATION
    )

    return " ".join(
        normalized.split()
    )


def _is_hidden_element(
    element: Tag,
) -> bool:
    """Comprueba si un elemento está oculto mediante HTML o estilos."""

    if element.has_attr("hidden"):
        return True

    if (
        str(
            element.get(
                "aria-hidden",
                "",
            )
        ).lower()
        == "true"
    ):
        return True

    style = str(
        element.get(
            "style",
            "",
        )
    ).lower().replace(
        " ",
        "",
    )

    return (
        "display:none" in style
        or "visibility:hidden" in style
        or "visibility:collapse" in style
    )


def _remove_html_noise(
    soup: BeautifulSoup,
) -> None:
    """Elimina elementos que no forman parte del contenido contractual."""

    for element in soup.find_all(
        list(NOISE_TAGS)
    ):
        element.decompose()

    role_noise: list[Tag] = []

    for element in soup.find_all(True):
        role = str(
            element.get(
                "role",
                "",
            )
        ).lower()

        if role in NOISE_ROLES:
            role_noise.append(element)

    for element in reversed(role_noise):
        element.decompose()

    hidden_elements = [
        element
        for element in soup.find_all(True)
        if _is_hidden_element(element)
    ]

    for element in reversed(
        hidden_elements
    ):
        element.decompose()

    # El header global suele pertenecer a la interfaz del sitio.
    # Un header dentro de main/article se conserva.
    headers_to_remove: list[Tag] = []

    for header in soup.find_all("header"):
        if (
            header.find_parent(
                ["main", "article"]
            )
            is None
        ):
            headers_to_remove.append(
                header
            )

    for header in reversed(
        headers_to_remove
    ):
        header.decompose()


def _visible_text_length(
    element: Tag,
) -> int:
    """Calcula la cantidad de texto visible de un elemento."""

    return len(
        normalize_text(
            element.get_text(
                " ",
                strip=True,
            )
        )
    )


def _select_content_root(
    soup: BeautifulSoup,
) -> Tag:
    """Selecciona el contenedor principal del documento."""

    candidates = [
        element
        for element in soup.find_all(
            ["main", "article"]
        )
        if _visible_text_length(element) > 0
    ]

    if candidates:
        return max(
            candidates,
            key=_visible_text_length,
        )

    if soup.body is None:
        raise ValueError(
            "El documento HTML no contiene body."
        )

    return soup.body


def _contains_only_links(
    element: Tag,
    text: str,
) -> bool:
    """Comprueba si todo el texto de un bloque procede de enlaces."""

    links = element.find_all("a")

    if not links:
        return False

    links_text = normalize_text(
        " ".join(
            link.get_text(
                " ",
                strip=True,
            )
            for link in links
        )
    )

    return (
        bool(text)
        and text == links_text
    )


def _is_fully_emphasized(
    element: Tag,
) -> bool:
    """Comprueba si todo el texto visible está resaltado."""

    text_nodes = [
        node
        for node in element.descendants
        if (
            isinstance(
                node,
                NavigableString,
            )
            and normalize_text(
                str(node)
            )
        )
    ]

    if not text_nodes:
        return False

    for node in text_nodes:
        parent = node.parent

        if not isinstance(
            parent,
            Tag,
        ):
            return False

        if (
            parent.name
            not in {
                "strong",
                "b",
            }
            and parent.find_parent(
                ["strong", "b"]
            )
            is None
        ):
            return False

    return True


def _build_table_row_text(
    row: Tag,
) -> str:
    """Construye el texto de una fila conservando el orden de las celdas."""

    cells = row.find_all(
        list(TABLE_CELL_TAGS),
        recursive=False,
    )

    parts = [
        normalize_text(
            cell.get_text(
                " ",
                strip=True,
            )
        )
        for cell in cells
    ]

    return " | ".join(
        part
        for part in parts
        if part
    )


def _get_generic_container_text(
    element: Tag,
) -> str:
    """Extrae únicamente el texto propio de un contenedor genérico."""

    structural_tags = (
        HEADING_TAGS
        | CONTENT_TAGS
        | GENERIC_TAGS
        | frozenset(
            {
                "table",
                "thead",
                "tbody",
                "tfoot",
                "tr",
                "td",
                "th",
            }
        )
    )

    parts: list[str] = []

    for child in element.children:
        if isinstance(
            child,
            Comment,
        ):
            continue

        if isinstance(
            child,
            NavigableString,
        ):
            parts.append(
                str(child)
            )
            continue

        if not isinstance(
            child,
            Tag,
        ):
            continue

        if (
            child.name
            in structural_tags
        ):
            continue

        if child.find(
            list(structural_tags)
        ) is not None:
            continue

        parts.append(
            child.get_text(
                " ",
                strip=True,
            )
        )

    return normalize_text(
        " ".join(parts)
    )


def _is_candidate(
    element: Tag,
) -> bool:
    """Comprueba si un elemento puede representar un bloque textual."""

    if element.name in HEADING_TAGS:
        return True

    if element.name in CONTENT_TAGS:
        if element.find_parent(
            list(TABLE_CELL_TAGS)
        ) is not None:
            return False

        return element.find_parent(
            list(CONTENT_TAGS)
        ) is None

    if element.name == "tr":
        cells = element.find_all(
            list(TABLE_CELL_TAGS),
            recursive=False,
        )

        return (
            bool(cells)
            and any(
                cell.name == "td"
                for cell in cells
            )
        )

    if element.name in GENERIC_TAGS:
        if element.find_parent(
            list(
                HEADING_TAGS
                | CONTENT_TAGS
            )
        ) is not None:
            return False

        return bool(
            _get_generic_container_text(
                element
            )
        )

    return False


def parse_contract_html(
    raw_html: str,
) -> tuple[
    str,
    str,
    list[ContractSection],
]:
    """Convierte HTML crudo en bloques estructurados del contrato."""

    if not raw_html.strip():
        raise ValueError(
            "No existe HTML para preprocesar."
        )

    soup = BeautifulSoup(
        raw_html,
        "html.parser",
    )

    title = (
        normalize_text(
            soup.title.get_text(
                " ",
                strip=True,
            )
        )
        if soup.title
        else "Sin título"
    )

    language = "unknown"

    if (
        soup.html
        and soup.html.get("lang")
    ):
        language = str(
            soup.html.get("lang")
        ).split("-")[0].lower()

    _remove_html_noise(soup)

    root = _select_content_root(
        soup
    )

    candidates = [
        element
        for element in root.find_all(True)
        if _is_candidate(element)
    ]

    sections: list[ContractSection] = []

    current_heading: str | None = None
    current_heading_level: int | None = None

    for element in candidates:
        if element.name in HEADING_TAGS:
            heading_text = normalize_text(
                element.get_text(
                    " ",
                    strip=True,
                )
            )

            if not heading_text:
                continue

            current_heading = heading_text
            current_heading_level = int(
                element.name[1]
            )
            continue

        if element.name == "tr":
            text = _build_table_row_text(
                element
            )
        elif element.name in GENERIC_TAGS:
            text = _get_generic_container_text(
                element
            )
        else:
            text = normalize_text(
                element.get_text(
                    " ",
                    strip=True,
                )
            )

        if not text:
            continue

        links = element.find_all("a")

        sections.append(
            ContractSection(
                order=len(sections) + 1,
                heading=current_heading,
                heading_level=(
                    current_heading_level
                ),
                content=text,
                html_tag=element.name,
                is_fully_emphasized=(
                    _is_fully_emphasized(
                        element
                    )
                ),
                source_area="content",
                is_link_only=(
                    _contains_only_links(
                        element,
                        text,
                    )
                ),
                link_count=len(links),
            )
        )

    if not sections:
        raise ValueError(
            "No se encontró contenido textual útil en el HTML."
        )

    return (
        title,
        language,
        sections,
    )


def _find_text_split_position(
    text: str,
    max_chars: int,
) -> int:
    """Busca un corte natural sin superar el limite."""

    minimum_position = max(
        1,
        max_chars // 2,
    )

    window = text[
        : max_chars + 1
    ]

    punctuation_positions: list[int] = []

    for marker in (
        ". ",
        "; ",
        ": ",
        "? ",
        "! ",
    ):
        position = window.rfind(
            marker,
            minimum_position,
        )

        if position >= 0:
            punctuation_positions.append(
                position + 1
            )

    if punctuation_positions:
        return max(
            punctuation_positions
        )

    whitespace_position = window.rfind(
        " ",
        minimum_position,
        max_chars + 1,
    )

    if whitespace_position > 0:
        return whitespace_position

    whitespace_position = window.rfind(
        " ",
        0,
        max_chars + 1,
    )

    if whitespace_position > 0:
        return whitespace_position

    return max_chars


def split_oversized_sections(
    sections: list[ContractSection],
    *,
    max_chars: int,
) -> list[ContractSection]:
    """Divide bloques grandes antes de la segmentacion semantica."""

    if max_chars <= 0:
        raise ValueError(
            "max_chars debe ser mayor que cero."
        )

    split_sections: list[
        ContractSection
    ] = []

    for section in sections:
        remaining = normalize_text(
            section.content
        )

        while len(remaining) > max_chars:
            split_position = (
                _find_text_split_position(
                    remaining,
                    max_chars,
                )
            )

            fragment = remaining[
                :split_position
            ].strip()

            if not fragment:
                split_position = max_chars
                fragment = remaining[
                    :split_position
                ].strip()

            split_sections.append(
                section.model_copy(
                    update={
                        "content": fragment,
                    }
                )
            )

            remaining = remaining[
                split_position:
            ].strip()

        if remaining:
            split_sections.append(
                section.model_copy(
                    update={
                        "content": remaining,
                    }
                )
            )

    return split_sections


def get_noise_reason(
    section: ContractSection,
) -> str | None:
    """Determina si un bloque extraído debe eliminarse."""

    if (
        section.is_link_only
        and len(
            section.content.split()
        )
        <= 12
    ):
        return (
            "Bloque breve compuesto "
            "únicamente por enlaces."
        )

    return None


def clean_contract_sections(
    sections: list[ContractSection],
) -> tuple[
    list[ContractSection],
    list[RemovedBlock],
]:
    """Normaliza bloques y elimina ruido residual y duplicados."""

    cleaned_sections: list[
        ContractSection
    ] = []

    removed_blocks: list[
        RemovedBlock
    ] = []

    previous_signature: tuple[
        str | None,
        int | None,
        str,
    ] | None = None

    for section in sections:
        content = normalize_text(
            section.content
        )

        heading = None

        if section.heading is not None:
            heading = (
                normalize_text(
                    section.heading
                )
                or None
            )

        if not content:
            continue

        normalized_section = (
            section.model_copy(
                update={
                    "heading": heading,
                    "content": content,
                }
            )
        )

        noise_reason = get_noise_reason(
            normalized_section
        )

        if noise_reason is not None:
            removed_blocks.append(
                RemovedBlock(
                    original_order=(
                        section.order
                    ),
                    content=content,
                    reason=noise_reason,
                )
            )
            continue

        current_signature = (
            heading,
            section.heading_level,
            content,
        )

        if (
            current_signature
            == previous_signature
        ):
            removed_blocks.append(
                RemovedBlock(
                    original_order=(
                        section.order
                    ),
                    content=content,
                    reason=(
                        "Duplicado exacto "
                        "consecutivo."
                    ),
                )
            )
            continue

        cleaned_sections.append(
            normalized_section
        )

        previous_signature = (
            current_signature
        )

    if not cleaned_sections:
        raise ValueError(
            "No se encontró contenido contractual "
            "después de la limpieza."
        )

    return (
        cleaned_sections,
        removed_blocks,
    )


def build_cleaned_document_text(
    sections: list[ContractSection],
) -> str:
    """Construye el texto limpio sin segmentarlo en cláusulas."""

    if not sections:
        raise ValueError(
            "No existen secciones contractuales "
            "para construir el texto."
        )

    parts: list[str] = []

    previous_order = 0

    for section in sections:
        if (
            section.order
            <= previous_order
        ):
            raise ValueError(
                "Las secciones deben conservar "
                "un orden original ascendente."
            )

        content = normalize_text(
            section.content
        )

        if content:
            parts.append(content)

        previous_order = section.order

    cleaned_text = "\n\n".join(
        parts
    )

    if not cleaned_text:
        raise ValueError(
            "No se encontró contenido contractual "
            "para construir el texto."
        )

    return cleaned_text
