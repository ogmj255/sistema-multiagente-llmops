import unicodedata

from app.schemas.contract import ContractSection
from app.schemas.preprocessing import (
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
    normalized = normalized.translate(SPECIAL_SPACE_TRANSLATION)
    return " ".join(normalized.split())


def get_noise_reason(
    section: ContractSection,
) -> str | None:
    """Determina si una sección es ruido mediante su estructura."""

    if section.source_area in STRUCTURAL_NOISE_AREAS:
        return f"Bloque ubicado en el área HTML '{section.source_area}'."

    if section.is_link_only and len(section.content.split()) <= 12:
        return "Bloque breve compuesto únicamente por enlaces."

    if (
        section.source_area == "body"
        and section.heading is None
        and section.link_count >= 10
        and len(section.content.split()) <= 10
    ):
        return (
            "Contenedor breve con alta densidad de enlaces "
            "fuera del contenido contractual."
        )

    return None


def clean_contract_sections(
    sections: list[ContractSection],
) -> tuple[list[ContractSection], list[RemovedBlock]]:
    """Elimina ruido estructural y duplicados consecutivos."""

    cleaned_sections: list[ContractSection] = []
    removed_blocks: list[RemovedBlock] = []
    previous_signature: tuple[str | None, int | None, str] | None = None

    for section in sections:
        content = normalize_text(section.content)

        heading = None
        if section.heading is not None:
            heading = normalize_text(section.heading) or None

        if not content:
            continue

        normalized_section = section.model_copy(
            update={
                "heading": heading,
                "content": content,
            }
        )

        noise_reason = get_noise_reason(normalized_section)

        if noise_reason is not None:
            removed_blocks.append(
                RemovedBlock(
                    original_order=section.order,
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

        if current_signature == previous_signature:
            removed_blocks.append(
                RemovedBlock(
                    original_order=section.order,
                    content=content,
                    reason="Duplicado exacto consecutivo.",
                )
            )
            continue

        cleaned_sections.append(normalized_section)
        previous_signature = current_signature

    if not cleaned_sections:
        raise ValueError("No se encontró contenido contractual después de la limpieza.")

    return cleaned_sections, removed_blocks


def build_cleaned_document_text(
    sections: list[ContractSection],
) -> str:
    """Construye el texto limpio sin segmentarlo en cláusulas."""

    if not sections:
        raise ValueError("No existen secciones contractuales para construir el texto.")

    parts: list[str] = []
    previous_order = 0

    for section in sections:
        if section.order <= previous_order:
            raise ValueError(
                "Las secciones deben conservar un orden original ascendente."
            )

        content = normalize_text(section.content)

        if content:
            parts.append(content)

        previous_order = section.order

    cleaned_text = "\n\n".join(parts)

    if not cleaned_text:
        raise ValueError(
            "No se encontró contenido contractual para construir el texto."
        )

    return cleaned_text
