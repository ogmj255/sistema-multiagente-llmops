from datetime import UTC, datetime

import pytest
from app.schemas.contract import (
    ContractSection,
    ExtractedContract,
    SourceArea,
)
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
        match="No se encontraron bloques de texto",
    ):
        parse_static_html(html)
def create_test_contract(
    section_count: int,
    character_count: int,
    source_area: SourceArea = "body",
) -> ExtractedContract:
    """Crea un contrato sencillo para las pruebas."""
    sections: list[ContractSection] = []

    for index in range(section_count):
        sections.append(
            ContractSection(
                order=index + 1,
                heading=f"Secci?n {index + 1}",
                content="Contenido de prueba.",
                source_area=source_area,
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
    """Acepta un contrato corto ubicado en una zona de contenido."""
    contract = create_test_contract(
        section_count=1,
        character_count=20,
        source_area="content",
    )

    assert has_sufficient_contract_content(contract) is True

def test_reject_insufficient_contract_content() -> None:
    """Rechaza texto que procede ?nicamente de navegaci?n."""
    contract = create_test_contract(
        section_count=2,
        character_count=700,
        source_area="navigation",
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



def test_extract_extended_html_elements() -> None:
    """Extrae bloques semanticos y filas completas de tablas."""
    html = """
    <html lang="en">
        <head>
            <title>Extended Terms</title>
        </head>
        <body>
            <main>
                <h5>Payment conditions</h5>

                <blockquote>
                    Payments are non-refundable.
                </blockquote>

                <dl>
                    <dt>Service</dt>
                    <dd>The online product provided to the user.</dd>
                </dl>

                <table>
                    <tr>
                        <th>Plan</th>
                        <td>Professional subscription</td>
                    </tr>
                </table>
            </main>
        </body>
    </html>
    """

    _, _, sections, full_text = parse_static_html(html)

    assert len(sections) == 4
    assert sections[0].html_tag == "blockquote"
    assert sections[0].heading == "Payment conditions"
    assert sections[0].heading_level == 5
    assert sections[1].html_tag == "dt"
    assert sections[2].html_tag == "dd"
    assert sections[3].html_tag == "tr"
    assert sections[3].content == "Plan | Professional subscription"
    assert "Payments are non-refundable." in full_text

def test_ignore_aria_role_as_heading() -> None:
    """No interpreta un rol ARIA como encabezado del contrato."""
    html = """
    <html>
        <body>
            <main>
                <div role="heading" aria-level="3">
                    Account security
                </div>
                <p>The user must protect the account.</p>
            </main>
        </body>
    </html>
    """

    _, _, sections, full_text = parse_static_html(html)

    assert len(sections) == 1
    assert sections[0].heading is None
    assert sections[0].content == (
        "The user must protect the account."
    )
    assert "Account security" not in full_text


def test_use_generic_fallback_without_semantic_content() -> None:
    """Usa div genericos cuando no existen bloques de contenido."""
    html = """
    <html>
        <body>
            <nav>
                <ul>
                    <li>Home</li>
                </ul>
            </nav>

            <main>
                <div>
                    <span>
                        The user must comply with these terms.
                    </span>
                </div>
            </main>
        </body>
    </html>
    """

    _, _, sections, full_text = parse_static_html(html)

    content_sections = [
        section
        for section in sections
        if section.source_area == "content"
    ]

    assert len(content_sections) == 1
    assert content_sections[0].html_tag == "div"
    assert "comply with these terms" in full_text

def test_ignore_link_collection_heading() -> None:
    """No asigna un encabezado perteneciente a un índice de enlaces."""

    html = """
    <html>
        <body>
            <main>
                <div>
                    <h2>Page contents</h2>
                    <a href="#one">Section one</a>
                    <a href="#two">Section two</a>
                    <a href="#three">Section three</a>
                </div>

                <div>
                    <p>This is contractual content.</p>
                </div>
            </main>
        </body>
    </html>
    """

    _, _, sections, _ = parse_static_html(html)

    assert len(sections) == 1
    assert sections[0].content == "This is contractual content."
    assert sections[0].heading is None


def test_ignore_hidden_html_content() -> None:
    """No extrae elementos HTML marcados como ocultos."""

    html = """
    <html>
        <body>
            <main>
                <p hidden>Hidden condition.</p>
                <p aria-hidden="true">Another hidden condition.</p>
                <p style="display: none">Invisible condition.</p>
                <p>Visible contractual condition.</p>
            </main>
        </body>
    </html>
    """

    _, _, sections, full_text = parse_static_html(html)

    assert len(sections) == 1
    assert sections[0].content == "Visible contractual condition."
    assert "Hidden condition" not in full_text
    assert "Invisible condition" not in full_text
