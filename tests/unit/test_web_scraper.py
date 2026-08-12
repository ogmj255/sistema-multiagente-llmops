from datetime import UTC, datetime

import pytest
from app.schemas.contract import ContractSection, ExtractedContract
from app.services.web_scraper import (
    has_sufficient_contract_content,
    parse_static_html,
)

SAMPLE_HTML = """
<html lang="es">
    <head>
        <title>Contrato de prueba</title>
        <script>contenido_no_permitido()</script>
    </head>
    <body>
        <nav>
            <p>Menú principal</p>
        </nav>
        <main>
            <h1>Términos de servicio</h1>
            <p>El usuario deberá respetar las condiciones del servicio.</p>

            <h2>Contenido del usuario</h2>
            <p>El usuario conserva la propiedad de su contenido.</p>
            <ul>
                <li>No se permite contenido ilegal.</li>
            </ul>
        </main>
        <footer>
            <p>Información del pie de página</p>
        </footer>
    </body>
</html>
"""


def test_parse_static_html() -> None:
    """Comprueba que el scraper conserve el texto visible."""

    title, language, sections, full_text = parse_static_html(
        SAMPLE_HTML
    )

    assert title == "Contrato de prueba"
    assert language == "es"
    assert len(sections) == 5
    assert sections[1].heading == "Términos de servicio"
    assert sections[2].heading == "Contenido del usuario"
    assert "Menú principal" in full_text
    assert "pie de página" in full_text
    assert "contenido_no_permitido" not in full_text


def test_reject_html_without_contract_content() -> None:
    html = "<html><body><main><h1>Documento vacío</h1></main></body></html>"

    with pytest.raises(
        ValueError,
        match="No se encontraron párrafos o listas",
    ):
        parse_static_html(html)
def create_test_contract(
    section_count: int,
    character_count: int,
) -> ExtractedContract:
    """Crea un contrato sencillo para las pruebas."""

    sections: list[ContractSection] = []

    for index in range(section_count):
        sections.append(
            ContractSection(
                order=index + 1,
                heading=f"Sección {index + 1}",
                content="Contenido de prueba.",
            )
        )

    return ExtractedContract(
        source_url="https://example.com/terms",
        platform="Example",
        title="Contrato de prueba",
        retrieved_at=datetime.now(UTC),
        extraction_method="beautiful_soup",
        language="es",
        sections=sections,
        full_text="A" * character_count,
    )


def test_accept_sufficient_contract_content() -> None:
    contract = create_test_contract(
        section_count=3,
        character_count=1_000,
    )

    assert has_sufficient_contract_content(contract) is True


def test_reject_insufficient_contract_content() -> None:
    contract = create_test_contract(
        section_count=2,
        character_count=700,
    )

    assert has_sufficient_contract_content(contract) is False

def test_avoid_duplicate_nested_paragraphs() -> None:
    """Evita duplicar un párrafo contenido dentro de una lista."""

    html = """
    <html>
        <body>
            <main>
                <h1>Términos de prueba</h1>
                <ul>
                    <li>
                        <p>Este contenido debe aparecer una sola vez.</p>
                    </li>
                </ul>
            </main>
        </body>
    </html>
    """

    _, _, sections, full_text = parse_static_html(html)

    assert len(sections) == 1
    assert full_text.count(
        "Este contenido debe aparecer una sola vez."
    ) == 1


def test_extract_content_from_entire_body() -> None:
    """Comprueba la extracción desde todo el cuerpo HTML."""

    html = """
    <html lang="es">
        <head>
            <title>Contrato con varios contenedores</title>
        </head>
        <body>
            <main>
                <p>Menú de navegación</p>
            </main>

            <main>
                <h1>Términos de servicio</h1>
                <p>Este es el contenido principal del contrato.</p>
                <p>Esta es una segunda condición del servicio.</p>
            </main>
        </body>
    </html>
    """

    title, language, sections, full_text = parse_static_html(
        html
    )

    assert title == "Contrato con varios contenedores"
    assert language == "es"
    assert len(sections) == 3
    assert "Menú de navegación" in full_text
    assert "contenido principal del contrato" in full_text
