import unicodedata

from app.schemas.contract import ContractSection
from app.schemas.preprocessing import (
    ProcessedClause,
    RemovedBlock,
)

SPECIAL_SPACE_TRANSLATION = str.maketrans(
    {
        "\u00a0": " ",
        "\u2007": " ",
        "\u202f": " ",
    }
)


STRUCTURAL_NOISE_AREAS = frozenset(
    {
        "navigation",
        "header",
        "footer",
        "aside",
        "interactive",
    }
)


def normalize_text(text: str) -> str:
    """Normaliza Unicode y espacios sin alterar el significado."""
    normalized = unicodedata.normalize("NFC", text)
    normalized = normalized.replace("\ufeff", "")
    normalized = normalized.translate(
        SPECIAL_SPACE_TRANSLATION
    )
    return " ".join(normalized.split())

def get_noise_reason(
    section: ContractSection,
) -> str | None:
    """Determina si una sección es ruido mediante su estructura."""

    if section.source_area in STRUCTURAL_NOISE_AREAS:
        return (
            "Bloque ubicado en el área HTML "
            f"'{section.source_area}'."
        )

    if (
        section.is_link_only
        and section.link_count >= 2
    ):
        return (
            "Bloque compuesto únicamente por múltiples enlaces."
        )

    if (
        section.source_area == "body"
        and section.is_link_only
        and section.heading is None
    ):
        return (
            "Enlace aislado fuera del contenido "
            "contractual principal."
        )

    return None


def clean_contract_sections(
    sections: list[ContractSection],
) -> tuple[list[ContractSection], list[RemovedBlock]]:
    """Elimina ruido estructural y duplicados consecutivos."""

    cleaned_sections: list[ContractSection] = []
    removed_blocks: list[RemovedBlock] = []
    previous_content: str | None = None

    for section in sections:
        content = normalize_text(section.content)

        heading = None
        if section.heading is not None:
            heading = (
                normalize_text(section.heading)
                or None
            )

        if not content:
            continue

        normalized_section = section.model_copy(
            update={
                "heading": heading,
                "content": content,
            }
        )

        noise_reason = get_noise_reason(
            normalized_section
        )

        if noise_reason is not None:
            removed_blocks.append(
                RemovedBlock(
                    original_order=section.order,
                    content=content,
                    reason=noise_reason,
                )
            )
            continue

        if content == previous_content:
            removed_blocks.append(
                RemovedBlock(
                    original_order=section.order,
                    content=content,
                    reason="Duplicado exacto consecutivo.",
                )
            )
            continue

        cleaned_sections.append(normalized_section)
        previous_content = content

    if not cleaned_sections:
        raise ValueError(
            "No se encontró contenido contractual "
            "después de la limpieza."
        )

    return cleaned_sections, removed_blocks


def segment_contract_sections(
    sections: list[ContractSection],
    default_heading: str | None = None,
    default_heading_level: int | None = None,
) -> list[ProcessedClause]:
    """Convierte bloques contractuales ordenados en cláusulas."""

    if not sections:
        raise ValueError(
            "No existen secciones contractuales para segmentar."
        )

    clauses: list[ProcessedClause] = []
    previous_original_order = 0

    for section in sections:
        if section.order <= previous_original_order:
            raise ValueError(
                "Las secciones deben conservar un orden "
                "original ascendente."
            )

        heading = section.heading
        heading_level = section.heading_level

        if heading is None:
            heading = default_heading
            heading_level = default_heading_level

        clauses.append(
            ProcessedClause(
                order=len(clauses) + 1,
                original_order=section.order,
                heading=heading,
                heading_level=heading_level,
                content=section.content,
            )
        )

        previous_original_order = section.order

    return clauses


def build_cleaned_text(
    clauses: list[ProcessedClause],
) -> str:
    """Construye el texto limpio conservando su jerarquía."""

    parts: list[str] = []
    previous_heading: str | None = None

    for clause in clauses:
        if (
            clause.heading is not None
            and clause.heading != previous_heading
        ):
            parts.append(clause.heading)

        parts.append(clause.content)
        previous_heading = clause.heading

    return "\n\n".join(parts)
