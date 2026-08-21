from app.schemas.contract import ContractSection
from app.services.text_preprocessor import (
    build_cleaned_text,
    clean_contract_sections,
    normalize_text,
    segment_contract_sections,
)


def test_normalize_text() -> None:
    """Comprueba la normalización de espacios."""

    text = "Texto\u00a0con   espacios\n\nrepetidos."

    assert normalize_text(text) == "Texto con espacios repetidos."


def test_remove_structural_noise() -> None:
    """Elimina navegación y pie de página sin usar palabras clave."""

    sections = [
        ContractSection(
            order=1,
            content="Contáctenos",
            html_tag="li",
            source_area="navigation",
            is_link_only=True,
        ),
        ContractSection(
            order=2,
            heading="Condiciones",
            content="El usuario debe proteger su cuenta.",
            html_tag="p",
            source_area="content",
        ),
        ContractSection(
            order=3,
            content="Información corporativa",
            html_tag="li",
            source_area="footer",
            is_link_only=True,
        ),
    ]

    cleaned, removed = clean_contract_sections(sections)

    assert len(cleaned) == 1
    assert cleaned[0].order == 2
    assert len(removed) == 2


def test_remove_isolated_body_link() -> None:
    """Elimina un enlace aislado fuera del contenido principal."""

    sections = [
        ContractSection(
            order=1,
            content="Cambiar idioma",
            html_tag="p",
            source_area="body",
            is_link_only=True,
        ),
        ContractSection(
            order=2,
            content="Condición contractual válida.",
            html_tag="p",
            source_area="body",
            is_link_only=False,
        ),
    ]

    cleaned, removed = clean_contract_sections(sections)

    assert len(cleaned) == 1
    assert cleaned[0].order == 2
    assert len(removed) == 1


def test_remove_consecutive_duplicates() -> None:
    """Elimina duplicados exactos consecutivos."""

    sections = [
        ContractSection(
            order=1,
            content="La misma condición.",
            source_area="content",
        ),
        ContractSection(
            order=2,
            content="La misma condición.",
            source_area="content",
        ),
    ]

    cleaned, removed = clean_contract_sections(sections)

    assert len(cleaned) == 1
    assert len(removed) == 1
    assert removed[0].original_order == 2


def test_segment_sections_preserving_order() -> None:
    """Segmenta según la estructura y conserva el orden original."""

    sections = [
        ContractSection(
            order=5,
            heading="Account Terms",
            content="The user must provide accurate information.",
            html_tag="p",
            source_area="content",
        ),
        ContractSection(
            order=6,
            heading="Account Terms",
            content="The user must protect the account.",
            html_tag="li",
            source_area="content",
        ),
    ]

    clauses = segment_contract_sections(sections)
    cleaned_text = build_cleaned_text(clauses)

    assert len(clauses) == 2
    assert clauses[0].order == 1
    assert clauses[0].original_order == 5
    assert clauses[1].original_order == 6
    assert cleaned_text.count("Account Terms") == 1


def test_preserve_large_contract_without_length_limit() -> None:
    """Conserva todas las secciones sin establecer límites artificiales."""

    sections = [
        ContractSection(
            order=index,
            heading="Condiciones",
            content=f"Condición contractual número {index}.",
            source_area="content",
        )
        for index in range(1, 201)
    ]

    cleaned, removed = clean_contract_sections(sections)
    clauses = segment_contract_sections(cleaned)

    assert len(cleaned) == 200
    assert len(clauses) == 200
    assert removed == []


def test_remove_multiple_link_selector() -> None:
    """Elimina selectores compuestos únicamente por enlaces."""

    sections = [
        ContractSection(
            order=1,
            content="English Español Français Português",
            source_area="content",
            is_link_only=True,
            link_count=4,
        ),
        ContractSection(
            order=2,
            content="Valid contractual condition.",
            source_area="content",
        ),
    ]

    cleaned, removed = clean_contract_sections(sections)

    assert len(cleaned) == 1
    assert cleaned[0].order == 2
    assert len(removed) == 1


def test_use_default_document_heading() -> None:
    """Utiliza el título cuando el HTML no incluye encabezado."""

    sections = [
        ContractSection(
            order=1,
            content="Valid contractual condition.",
            source_area="content",
        )
    ]

    clauses = segment_contract_sections(
        sections,
        default_heading="Terms of Service",
        default_heading_level=1,
    )

    assert clauses[0].heading == "Terms of Service"
    assert clauses[0].heading_level == 1
