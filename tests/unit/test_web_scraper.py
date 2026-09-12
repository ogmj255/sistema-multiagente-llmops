from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from app.schemas.contract import (
    ContractSection,
    ExtractedContract,
    ExtractionRequest,
    SourceArea,
)
from app.services import web_scraper
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

    title, language, sections, full_text = parse_static_html(SAMPLE_HTML)

    assert title == "Contrato de prueba"
    assert language == "es"
    assert len(sections) == 5
    assert sections[1].heading == "Términos de servicio"
    assert sections[2].heading == "Contenido del usuario"
    assert "Menú principal" not in full_text
    assert any(
        section.content == "Menú principal"
        and section.source_area == "navigation"
        for section in sections
    )
    assert "El usuario deberá respetar las condiciones del servicio." in full_text
    assert "El usuario conserva la propiedad de su contenido." in full_text


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
    assert full_text.count("Este contenido debe aparecer una sola vez.") == 1


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

    title, language, sections, full_text = parse_static_html(html)

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


def test_preserve_aria_text_without_using_it_as_heading() -> None:
    """Conserva el texto ARIA sin convertirlo en encabezado."""

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

    assert len(sections) == 2
    assert sections[0].content == "Account security"
    assert sections[0].heading is None
    assert sections[0].heading_level is None
    assert sections[1].content == ("The user must protect the account.")
    assert "Account security" in full_text


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
        section for section in sections if section.source_area == "content"
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


def test_preserve_standard_heading_behavior() -> None:
    """Mantiene un encabezado normal como contexto."""

    html = """
    <html>
        <body>
            <main>
                <h2>Account terms</h2>
                <h3>Account security</h3>
                <p>
                    The user must protect the account
                    and its authentication credentials.
                </p>
            </main>
        </body>
    </html>
    """

    _, _, sections, _ = parse_static_html(html)

    assert len(sections) == 1
    assert sections[0].heading == "Account security"
    assert sections[0].heading_level == 3
    assert sections[0].html_tag == "p"


def test_preserve_headings_used_as_paragraphs() -> None:
    """Conserva un nivel de encabezado usado como contenido."""

    html = """
    <html>
        <body>
            <main>
                <h1>Terms of Service</h1>
                <h2>Account terms</h2>

                <h3>
                    The user must provide accurate account
                    information when registering.
                </h3>

                <h3>
                    The user is responsible for protecting
                    the account credentials.
                </h3>

                <li>Additional condition.</li>
            </main>
        </body>
    </html>
    """

    _, _, sections, full_text = parse_static_html(html)

    assert len(sections) == 3
    assert sections[0].html_tag == "h3"
    assert sections[0].heading == "Account terms"
    assert sections[0].heading_level == 2
    assert "accurate account information" in full_text
    assert "protecting the account credentials" in full_text


def test_extract_semantic_and_generic_content_together() -> None:
    """Conserva contenido semántico y genérico en el mismo documento."""

    html = """
    <html>
        <body>
            <main>
                <h1>Terms of Service</h1>

                <p>
                    This paragraph uses semantic HTML.
                </p>

                <div>
                    <span>
                        This condition uses a generic container.
                    </span>
                </div>
            </main>
        </body>
    </html>
    """

    _, _, sections, full_text = parse_static_html(html)

    assert len(sections) == 2
    assert sections[0].html_tag == "p"
    assert sections[1].html_tag == "div"
    assert "semantic HTML" in full_text
    assert "generic container" in full_text


def test_dynamic_extraction_rejects_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rechaza una navegación dinámica bloqueada."""

    playwright_manager = MagicMock()
    playwright = playwright_manager.__enter__.return_value
    browser = playwright.chromium.launch.return_value
    page = browser.new_page.return_value

    navigation_response = MagicMock()
    navigation_response.ok = False
    navigation_response.status = 403
    page.goto.return_value = navigation_response

    monkeypatch.setattr(
        web_scraper,
        "sync_playwright",
        lambda: playwright_manager,
    )

    with pytest.raises(
        ValueError,
        match="HTTP 403",
    ):
        web_scraper.extract_dynamic_contract(
            ExtractionRequest(
                url="https://example.com/terms",
                platform="Example",
            )
        )

    page.content.assert_not_called()
    browser.close.assert_called_once_with()


def test_identify_fully_emphasized_paragraph() -> None:
    """Distingue énfasis completo de énfasis parcial."""

    html = """
    <html>
        <body>
            <main>
                <h1>Terms</h1>

                <p>
                    <strong>Payment conditions</strong>
                </p>

                <p>
                    Read <strong>these conditions</strong>
                    carefully.
                </p>
            </main>
        </body>
    </html>
    """

    _, _, sections, _ = parse_static_html(html)

    assert len(sections) == 2
    assert sections[0].is_fully_emphasized is True
    assert sections[1].is_fully_emphasized is False
def test_detect_cookie_banner_as_non_contract_content() -> None:
    """Evita considerar un banner de cookies como contenido contractual."""

    html = """
    <html>
        <body>
            <div class="cookie-banner">
                Acepta las cookies para continuar.
            </div>

            <main>
                <p>El usuario deberá cumplir los términos del servicio.</p>
            </main>
        </body>
    </html>
    """

    _, _, sections, _ = parse_static_html(html)

    cookie_section = next(
        section
        for section in sections
        if "Acepta las cookies" in section.content
    )

    assert cookie_section.source_area not in {"content", "body"}


def test_detect_sidebar_div_as_non_contract_content() -> None:
    """Evita tratar un sidebar genérico como contenido contractual."""

    html = """
    <html>
        <body>
            <div class="sidebar">
                Artículos relacionados
            </div>

            <main>
                <p>El servicio podrá suspender cuentas que incumplan las reglas.</p>
            </main>
        </body>
    </html>
    """

    _, _, sections, _ = parse_static_html(html)

    sidebar_section = next(
        section
        for section in sections
        if "Artículos relacionados" in section.content
    )

    assert sidebar_section.source_area not in {"content", "body"}


def test_detect_footer_div_without_semantic_footer_tag() -> None:
    """Detecta un pie de página construido con div en lugar de footer."""

    html = """
    <html>
        <body>
            <main>
                <p>Estos términos regulan el uso del servicio.</p>
            </main>

            <div class="footer-links">
                Contacto y redes sociales
            </div>
        </body>
    </html>
    """

    _, _, sections, _ = parse_static_html(html)

    footer_section = next(
        section
        for section in sections
        if "Contacto y redes sociales" in section.content
    )

    assert footer_section.source_area not in {"content", "body"}


def test_reject_tiny_body_content_as_contract() -> None:
    """Rechaza una extracción demasiado pequeña para ser un contrato."""

    contract = ExtractedContract(
        source_url="https://example.com/terms",
        platform="Example",
        title="Terms",
        retrieved_at=datetime.now(UTC),
        extraction_method="beautiful_soup",
        language="en",
        sections=[
            ContractSection(
                order=1,
                content="Terms",
                source_area="body",
            )
        ],
        full_text="Terms",
    )

    assert has_sufficient_contract_content(contract) is False


def test_preserve_direct_text_in_container_with_child_paragraph() -> None:
    """Evita perder texto directo de un contenedor con hijos estructurados."""

    html = """
    <html>
        <body>
            <main>
                <div class="legal-content">
                    Este acuerdo regula la relación entre las partes.
                    <p>
                        El usuario acepta cumplir las condiciones del servicio.
                    </p>
                </div>
            </main>
        </body>
    </html>
    """

    _, _, _, full_text = parse_static_html(html)

    assert "Este acuerdo regula la relación entre las partes." in full_text
    assert "El usuario acepta cumplir las condiciones del servicio." in full_text


def test_nested_emphasis_is_detected_as_fully_emphasized() -> None:
    """Reconoce texto completamente resaltado aunque strong y b estén anidados."""

    html = """
    <html>
        <body>
            <main>
                <p>
                    <strong>
                        Limitación de <b>responsabilidad</b>
                    </strong>
                </p>
            </main>
        </body>
    </html>
    """

    _, _, sections, _ = parse_static_html(html)

    assert len(sections) == 1
    assert sections[0].is_fully_emphasized is True
def test_generic_container_does_not_duplicate_nested_structured_content() -> None:
    """Evita duplicar texto estructurado dentro de wrappers genéricos."""

    html = """
    <html>
        <body>
            <main>
                <div>
                    Texto directo del contenedor.

                    <span>
                        <div>
                            <p>Contenido contractual anidado.</p>
                        </div>
                    </span>
                </div>
            </main>
        </body>
    </html>
    """

    _, _, sections, full_text = parse_static_html(html)

    assert full_text.count("Texto directo del contenedor.") == 1
    assert full_text.count("Contenido contractual anidado.") == 1

    matching_sections = [
        section
        for section in sections
        if section.content == "Contenido contractual anidado."
    ]

    assert len(matching_sections) == 1

def test_preserve_section_heading_inside_main_with_header_class() -> None:
    """No confunde encabezados de sección con la cabecera del sitio."""

    html = """
    <html>
        <body>
            <main>
                <h1>Master Subscription Agreement</h1>

                <div class="notion-sub_header-block">
                    <h3>9. Limitation of Liability</h3>
                </div>

                <div>
                    Neither party will be liable for consequential damages.
                </div>
            </main>
        </body>
    </html>
    """

    _, _, sections, _ = parse_static_html(html)

    clause = next(
        section
        for section in sections
        if "Neither party will be liable" in section.content
    )

    assert clause.source_area == "content"
    assert clause.heading == "9. Limitation of Liability"
    assert clause.heading_level == 3
