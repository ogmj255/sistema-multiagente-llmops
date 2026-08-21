import pytest
from app.schemas.contract import ContractSection
from app.services.text_preprocessor import (
    build_cleaned_text,
    clean_contract_sections,
    normalize_text,
    segment_contract_sections,
)


def test_normalize_text() -> None:
    """Normaliza espacios especiales y saltos de linea."""
    text = (
        "Texto\u00a0con\t espacios\r\n"
        "\u202frepetidos."
    )

    assert normalize_text(text) == (
        "Texto con espacios repetidos."
    )


def test_normalize_unicode_composition() -> None:
    """Convierte caracteres descompuestos a Unicode NFC."""
    text = "Cafe\u0301, informacio\u0301n y nin\u0303o."

    assert normalize_text(text) == (
        "Caf\u00e9, informaci\u00f3n y ni\u00f1o."
    )


def test_remove_byte_order_mark() -> None:
    """Elimina marcas BOM incorporadas al texto."""
    text = "\ufeffTerms of Service\ufeff"

    assert normalize_text(text) == "Terms of Service"


def test_preserve_legal_characters() -> None:
    """Conserva simbolos, cantidades, comillas y enlaces."""
    text = (
        "\u201cUser\u201d agrees to \u00a7 5, "
        "pays \u20ac10.00 and visits "
        "https://example.com/terms?id=1."
    )

    assert normalize_text(text) == text


def test_clean_sections_normalizes_heading_and_content() -> None:
    """Aplica la normalizacion dentro del pipeline de limpieza."""
    sections = [
        ContractSection(
            order=1,
            heading="Informacio\u0301n de la cuenta",
            content=(
                "\ufeffEl\u00a0usuario debe\r\n"
                "proteger su cuenta."
            ),
            source_area="content",
        )
    ]

    cleaned, removed = clean_contract_sections(sections)

    assert len(cleaned) == 1
    assert removed == []
    assert cleaned[0].heading == (
        "Informaci\u00f3n de la cuenta"
    )
    assert cleaned[0].content == (
        "El usuario debe proteger su cuenta."
    )


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
def test_reject_empty_segmentation_input() -> None:
    """Rechaza una entrada sin secciones contractuales."""

    with pytest.raises(
        ValueError,
        match="No existen secciones contractuales",
    ):
        segment_contract_sections([])


def test_reject_sections_with_inconsistent_order() -> None:
    """Rechaza secciones cuyo orden original no es ascendente."""

    sections = [
        ContractSection(
            order=2,
            heading="Condiciones",
            content="Segunda condición.",
            html_tag="p",
            source_area="content",
        ),
        ContractSection(
            order=1,
            heading="Condiciones",
            content="Primera condición.",
            html_tag="p",
            source_area="content",
        ),
    ]

    with pytest.raises(
        ValueError,
        match="orden original ascendente",
    ):
        segment_contract_sections(sections)


def test_segment_list_and_table_row_as_complete_clauses() -> None:
    """Conserva listas y filas de tabla como cláusulas completas."""

    sections = [
        ContractSection(
            order=10,
            heading="2. Condiciones de pago",
            heading_level=2,
            content="2.1 El cliente deberá pagar la tarifa acordada.",
            html_tag="li",
            source_area="content",
        ),
        ContractSection(
            order=11,
            heading="2. Condiciones de pago",
            heading_level=2,
            content="Plan anual | USD 100",
            html_tag="tr",
            source_area="content",
        ),
    ]

    clauses = segment_contract_sections(sections)

    assert len(clauses) == 2
    assert clauses[0].order == 1
    assert clauses[0].original_order == 10
    assert clauses[0].content == (
        "2.1 El cliente deberá pagar la tarifa acordada."
    )
    assert clauses[1].order == 2
    assert clauses[1].original_order == 11
    assert clauses[1].content == "Plan anual | USD 100"
    assert all(
        clause.heading == "2. Condiciones de pago"
        for clause in clauses
    )