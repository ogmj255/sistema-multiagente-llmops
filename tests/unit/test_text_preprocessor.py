import pytest
from app.schemas.contract import ContractSection
from app.services.text_preprocessor import (
    build_cleaned_document_text,
    clean_contract_sections,
    normalize_text,
    parse_contract_html,
    split_oversized_sections,
)


def test_normalize_text() -> None:
    text = "Texto\u00a0con\t espacios\r\n\u202frepetidos."

    assert normalize_text(text) == "Texto con espacios repetidos."


def test_normalize_unicode_composition() -> None:
    text = "Cafe\u0301, informacio\u0301n y nin\u0303o."

    assert normalize_text(text) == (
        "Café, información y niño."
    )


def test_remove_byte_order_mark() -> None:
    text = "\ufeffTerms of Service\ufeff"

    assert normalize_text(text) == "Terms of Service"


def test_preserve_legal_characters() -> None:
    text = (
        "“User” agrees to § 5, "
        "pays €10.00 and visits "
        "https://example.com/terms?id=1."
    )

    assert normalize_text(text) == text


def test_parse_contract_html_gets_title_language_and_content() -> None:
    html = """
    <html lang="es">
        <head>
            <title>Contrato de prueba</title>
        </head>
        <body>
            <main>
                <h1>Términos de servicio</h1>
                <p>
                    El usuario deberá respetar
                    las condiciones del servicio.
                </p>
            </main>
        </body>
    </html>
    """

    title, language, sections = parse_contract_html(
        html
    )

    assert title == "Contrato de prueba"
    assert language == "es"
    assert len(sections) == 1
    assert sections[0].heading == "Términos de servicio"
    assert sections[0].heading_level == 1
    assert sections[0].content == (
        "El usuario deberá respetar "
        "las condiciones del servicio."
    )


def test_parse_contract_html_removes_structural_noise() -> None:
    html = """
    <html>
        <body>
            <nav>
                <a href="/home">Home</a>
            </nav>

            <main>
                <p>Condición contractual válida.</p>
            </main>

            <aside>
                Artículos relacionados
            </aside>

            <footer>
                Información corporativa
            </footer>
        </body>
    </html>
    """

    _, _, sections = parse_contract_html(
        html
    )

    assert len(sections) == 1
    assert sections[0].content == (
        "Condición contractual válida."
    )


def test_parse_contract_html_ignores_hidden_content() -> None:
    html = """
    <html>
        <body>
            <main>
                <p hidden>Hidden condition.</p>
                <p aria-hidden="true">
                    Another hidden condition.
                </p>
                <p style="display: none">
                    Invisible condition.
                </p>
                <p>
                    Visible contractual condition.
                </p>
            </main>
        </body>
    </html>
    """

    _, _, sections = parse_contract_html(
        html
    )

    assert len(sections) == 1
    assert sections[0].content == (
        "Visible contractual condition."
    )


def test_parse_contract_html_preserves_heading_context() -> None:
    html = """
    <html>
        <body>
            <main>
                <h2>Account terms</h2>
                <h3>Account security</h3>
                <p>
                    The user must protect the account.
                </p>
            </main>
        </body>
    </html>
    """

    _, _, sections = parse_contract_html(
        html
    )

    assert len(sections) == 1
    assert sections[0].heading == "Account security"
    assert sections[0].heading_level == 3


def test_parse_contract_html_avoids_nested_paragraph_duplicates() -> None:
    html = """
    <html>
        <body>
            <main>
                <ul>
                    <li>
                        <p>
                            Este contenido debe aparecer
                            una sola vez.
                        </p>
                    </li>
                </ul>
            </main>
        </body>
    </html>
    """

    _, _, sections = parse_contract_html(
        html
    )

    assert len(sections) == 1
    assert sections[0].content == (
        "Este contenido debe aparecer una sola vez."
    )


def test_parse_contract_html_extracts_extended_elements() -> None:
    html = """
    <html lang="en">
        <body>
            <main>
                <h5>Payment conditions</h5>

                <blockquote>
                    Payments are non-refundable.
                </blockquote>

                <dl>
                    <dt>Service</dt>
                    <dd>
                        The online product provided to the user.
                    </dd>
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

    _, _, sections = parse_contract_html(
        html
    )

    assert len(sections) == 4
    assert sections[0].html_tag == "blockquote"
    assert sections[0].heading == "Payment conditions"
    assert sections[0].heading_level == 5
    assert sections[1].html_tag == "dt"
    assert sections[2].html_tag == "dd"
    assert sections[3].html_tag == "tr"
    assert sections[3].content == (
        "Plan | Professional subscription"
    )


def test_parse_contract_html_uses_generic_container() -> None:
    html = """
    <html>
        <body>
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

    _, _, sections = parse_contract_html(
        html
    )

    assert len(sections) == 1
    assert sections[0].html_tag == "div"
    assert sections[0].content == (
        "The user must comply with these terms."
    )


def test_parse_contract_html_preserves_direct_container_text() -> None:
    html = """
    <html>
        <body>
            <main>
                <div>
                    Este acuerdo regula la relación entre las partes.
                    <p>
                        El usuario acepta cumplir las condiciones.
                    </p>
                </div>
            </main>
        </body>
    </html>
    """

    _, _, sections = parse_contract_html(
        html
    )

    contents = [
        section.content
        for section in sections
    ]

    assert (
        "Este acuerdo regula la relación entre las partes."
        in contents
    )

    assert (
        "El usuario acepta cumplir las condiciones."
        in contents
    )


def test_parse_contract_html_detects_full_emphasis() -> None:
    html = """
    <html>
        <body>
            <main>
                <p>
                    <strong>
                        Limitación de <b>responsabilidad</b>
                    </strong>
                </p>

                <p>
                    Read <strong>these conditions</strong>
                    carefully.
                </p>
            </main>
        </body>
    </html>
    """

    _, _, sections = parse_contract_html(
        html
    )

    assert len(sections) == 2
    assert sections[0].is_fully_emphasized is True
    assert sections[1].is_fully_emphasized is False


def test_parse_contract_html_rejects_document_without_text() -> None:
    html = """
    <html>
        <body>
            <main>
                <h1>Terms</h1>
            </main>
        </body>
    </html>
    """

    with pytest.raises(
        ValueError,
        match="contenido textual útil",
    ):
        parse_contract_html(
            html
        )


def test_parse_contract_html_selects_largest_main_container() -> None:
    html = """
    <html>
        <body>
            <main>
                <p>Short menu-like content.</p>
            </main>

            <main>
                <h1>Terms</h1>
                <p>
                    This is the main contractual content
                    of the document.
                </p>
                <p>
                    This is another contractual condition.
                </p>
            </main>
        </body>
    </html>
    """

    _, _, sections = parse_contract_html(
        html
    )

    contents = " ".join(
        section.content
        for section in sections
    )

    assert "main contractual content" in contents
    assert "another contractual condition" in contents
    assert "Short menu-like content" not in contents


def test_clean_sections_normalizes_heading_and_content() -> None:
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

    cleaned, removed = clean_contract_sections(
        sections
    )

    assert len(cleaned) == 1
    assert removed == []
    assert cleaned[0].heading == (
        "Información de la cuenta"
    )
    assert cleaned[0].content == (
        "El usuario debe proteger su cuenta."
    )


def test_clean_sections_removes_short_link_only_block() -> None:
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

    cleaned, removed = clean_contract_sections(
        sections
    )

    assert len(cleaned) == 1
    assert cleaned[0].order == 2
    assert len(removed) == 1
    assert removed[0].original_order == 1


def test_clean_sections_removes_consecutive_duplicates() -> None:
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

    cleaned, removed = clean_contract_sections(
        sections
    )

    assert len(cleaned) == 1
    assert len(removed) == 1
    assert removed[0].original_order == 2


def test_clean_sections_preserves_same_content_under_different_headings() -> None:
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

    cleaned, removed = clean_contract_sections(
        sections
    )

    assert len(cleaned) == 2
    assert removed == []
    assert cleaned[0].heading == "Cancelación"
    assert cleaned[1].heading == "Terminación"


def test_build_cleaned_document_text_preserves_block_order() -> None:
    sections = [
        ContractSection(
            order=1,
            heading="Terms",
            content="El usuario deberá tener",
            source_area="content",
        ),
        ContractSection(
            order=2,
            heading="Terms",
            content="18 años y ser capaz de contratar.",
            source_area="content",
        ),
        ContractSection(
            order=3,
            heading="Oferta",
            content="PLAN PREMIUM | USD 20",
            source_area="content",
        ),
    ]

    text = build_cleaned_document_text(
        sections
    )

    assert text == (
        "El usuario deberá tener\n\n"
        "18 años y ser capaz de contratar.\n\n"
        "PLAN PREMIUM | USD 20"
    )


def test_build_cleaned_document_text_does_not_inject_heading_metadata() -> None:
    sections = [
        ContractSection(
            order=1,
            heading="Condiciones generales",
            heading_level=1,
            content=(
                "El usuario deberá cumplir las condiciones."
            ),
            source_area="content",
        )
    ]

    text = build_cleaned_document_text(
        sections
    )

    assert text == (
        "El usuario deberá cumplir las condiciones."
    )

def test_split_oversized_sections_respects_maximum_length() -> None:
    """Cada fragmento debe respetar el limite configurado."""

    content = (
        "The subscriber must comply with all service conditions. "
        * 20
    )

    sections = [
        ContractSection(
            order=1,
            heading="Service conditions",
            heading_level=2,
            content=content,
            html_tag="p",
            source_area="content",
        )
    ]

    fragments = split_oversized_sections(
        sections,
        max_chars=120,
    )

    assert len(fragments) > 1
    assert all(
        len(fragment.content) <= 120
        for fragment in fragments
    )


def test_split_oversized_sections_preserves_content() -> None:
    """La division no debe perder ni duplicar texto."""

    content = (
        "First contractual condition applies. "
        "Second contractual condition also applies. "
        "The subscriber must protect the account and "
        "maintain accurate information. "
    ) * 10

    normalized_content = normalize_text(
        content
    )

    sections = [
        ContractSection(
            order=1,
            content=normalized_content,
            source_area="content",
        )
    ]

    fragments = split_oversized_sections(
        sections,
        max_chars=100,
    )

    reconstructed = normalize_text(
        " ".join(
            fragment.content
            for fragment in fragments
        )
    )

    assert reconstructed == normalized_content


def test_split_oversized_sections_preserves_source_metadata() -> None:
    """Los fragmentos deben conservar el origen del bloque."""

    content = (
        "The subscriber accepts the contractual obligations. "
        * 12
    )

    section = ContractSection(
        order=7,
        heading="Account obligations",
        heading_level=3,
        content=content,
        html_tag="p",
        is_fully_emphasized=True,
        source_area="content",
        is_link_only=False,
        link_count=2,
    )

    fragments = split_oversized_sections(
        [section],
        max_chars=90,
    )

    assert len(fragments) > 1

    for fragment in fragments:
        assert fragment.order == 7
        assert fragment.heading == "Account obligations"
        assert fragment.heading_level == 3
        assert fragment.html_tag == "p"
        assert fragment.is_fully_emphasized is True
        assert fragment.source_area == "content"
        assert fragment.is_link_only is False
        assert fragment.link_count == 2


def test_parse_contract_html_ignores_html_comments() -> None:
    """Los comentarios HTML no deben convertirse en texto contractual."""

    html = """
    <html lang="en">
        <body>
            <main>
                <div>
                    <!--$-->
                    Contractual content remains available.
                    <!--/$-->
                </div>
            </main>
        </body>
    </html>
    """

    _, _, sections = parse_contract_html(
        html
    )

    assert len(sections) == 1
    assert sections[0].content == (
        "Contractual content remains available."
    )
    assert "$" not in sections[0].content
