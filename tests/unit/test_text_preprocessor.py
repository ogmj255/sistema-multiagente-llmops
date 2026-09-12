from app.schemas.contract import ContractSection
from app.services.text_preprocessor import (
    build_cleaned_document_text,
    clean_contract_sections,
    normalize_text,
)


def test_normalize_text() -> None:
    """Normaliza espacios especiales y saltos de linea."""
    text = "Texto\u00a0con\t espacios\r\n\u202frepetidos."

    assert normalize_text(text) == ("Texto con espacios repetidos.")


def test_normalize_unicode_composition() -> None:
    """Convierte caracteres descompuestos a Unicode NFC."""
    text = "Cafe\u0301, informacio\u0301n y nin\u0303o."

    assert normalize_text(text) == ("Caf\u00e9, informaci\u00f3n y ni\u00f1o.")


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
            content=("\ufeffEl\u00a0usuario debe\r\nproteger su cuenta."),
            source_area="content",
        )
    ]

    cleaned, removed = clean_contract_sections(sections)

    assert len(cleaned) == 1
    assert removed == []
    assert cleaned[0].heading == ("Informaci\u00f3n de la cuenta")
    assert cleaned[0].content == ("El usuario debe proteger su cuenta.")


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


















def test_preserve_same_content_under_different_headings() -> None:
    """Conserva textos iguales cuando pertenecen a secciones distintas."""

    sections = [
        ContractSection(
            order=1,
            heading="Cancelación",
            heading_level=2,
            content="No se realizarán reembolsos.",
            source_area="content",
        ),
        ContractSection(
            order=2,
            heading="Terminación",
            heading_level=2,
            content="No se realizarán reembolsos.",
            source_area="content",
        ),
    ]

    cleaned, removed = clean_contract_sections(sections)

    assert len(cleaned) == 2
    assert removed == []
    assert cleaned[0].heading == "Cancelación"
    assert cleaned[1].heading == "Terminación"









def test_build_cleaned_document_text_preserves_block_order() -> None:
    """Construye el documento sin decidir l?mites de cl?usulas."""

    sections = [
        ContractSection(
            order=1,
            heading="Terms",
            content="El usuario deber? tener",
            html_tag="p",
            source_area="content",
        ),
        ContractSection(
            order=2,
            heading="Terms",
            content="18 a?os y ser capaz de contratar.",
            html_tag="p",
            source_area="content",
        ),
        ContractSection(
            order=3,
            heading="Oferta",
            content="PLAN PREMIUM | USD 20",
            html_tag="tr",
            source_area="content",
        ),
    ]

    text = build_cleaned_document_text(sections)

    assert text == (
        "El usuario deber? tener\n\n"
        "18 a?os y ser capaz de contratar.\n\n"
        "PLAN PREMIUM | USD 20"
    )


def test_build_cleaned_document_text_does_not_inject_heading_metadata() -> None:
    """No duplica encabezados almacenados como metadatos."""

    sections = [
        ContractSection(
            order=1,
            heading="Condiciones generales",
            heading_level=1,
            content="El usuario deber? cumplir las condiciones.",
            source_area="content",
        )
    ]

    text = build_cleaned_document_text(sections)

    assert text == "El usuario deber? cumplir las condiciones."
