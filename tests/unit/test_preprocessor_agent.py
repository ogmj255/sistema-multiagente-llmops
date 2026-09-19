from datetime import UTC, datetime

from app.agents import preprocessor_agent
from app.agents.preprocessor_agent import (
    run_preprocessor_agent,
)
from app.schemas.contract import (
    ContractSection,
    ExtractedContract,
)


def create_contract(
    raw_html: str,
) -> ExtractedContract:
    """Crea un documento HTML para probar el preprocesador."""

    return ExtractedContract(
        source_url="https://example.com/terms",
        platform="Example",
        retrieved_at=datetime.now(UTC),
        extraction_method="httpx",
        raw_html=raw_html,
    )


def test_preprocessor_cleans_and_segments_contract() -> None:
    """Comprueba el pipeline completo desde HTML crudo."""

    contract = create_contract(
        """
        <html lang="en">
            <head>
                <title>Terms of Service</title>
            </head>
            <body>
                <nav>
                    <a href="/products">Products and services</a>
                </nav>

                <main>
                    <h2>Account Terms</h2>

                    <p>
                        The user must provide accurate information.
                    </p>

                    <p>
                        The user must protect the account.
                    </p>
                </main>

                <footer>
                    <a href="/company">Company information</a>
                </footer>
            </body>
        </html>
        """
    )

    response = run_preprocessor_agent(contract)

    assert response.status == "success"
    assert response.result is not None

    assert response.result.title == "Terms of Service"
    assert response.result.language == "en"

    assert len(response.result.clauses) == 1

    clause = response.result.clauses[0]

    assert clause.order == 1
    assert clause.original_order == 1
    assert clause.heading is None
    assert clause.content == (
        "The user must provide accurate information. "
        "The user must protect the account."
    )

    assert response.result.cleaned_text == (
        "The user must provide accurate information.\n\n"
        "The user must protect the account."
    )

    assert response.result.removed_blocks == []


def test_preprocessor_preserves_logical_order() -> None:
    """Comprueba que el texto mantenga el orden original."""

    contract = create_contract(
        """
        <html lang="en">
            <head>
                <title>Terms</title>
            </head>
            <body>
                <main>
                    <h2>First section</h2>
                    <p>First contractual condition.</p>

                    <h2>Second section</h2>
                    <p>Second contractual condition.</p>
                </main>
            </body>
        </html>
        """
    )

    response = run_preprocessor_agent(contract)

    assert response.status == "success"
    assert response.result is not None

    chunked_text = " ".join(
        clause.content
        for clause in response.result.clauses
    )

    first_position = chunked_text.index(
        "First contractual condition."
    )
    second_position = chunked_text.index(
        "Second contractual condition."
    )

    assert first_position < second_position


def test_preprocessor_returns_error_without_contract_content() -> None:
    """Comprueba la respuesta cuando el HTML solo contiene ruido."""

    contract = create_contract(
        """
        <html lang="en">
            <head>
                <title>Terms</title>
            </head>
            <body>
                <nav>
                    <a href="/one">Navigation option</a>
                </nav>

                <footer>
                    <a href="/two">Footer option</a>
                </footer>
            </body>
        </html>
        """
    )

    response = run_preprocessor_agent(contract)

    assert response.status == "error"
    assert response.result is None
    assert response.error is not None
    assert "No se encontró contenido textual útil" in response.error


def test_preprocessor_controls_inconsistent_section_order(
    monkeypatch,
) -> None:
    """Devuelve un error controlado ante un orden interno inconsistente."""

    contract = create_contract(
        """
        <html>
            <body>
                <main>
                    <p>Contenido de prueba.</p>
                </main>
            </body>
        </html>
        """
    )

    sections = [
        ContractSection(
            order=2,
            heading="Second section",
            heading_level=2,
            content="Second contractual condition.",
            source_area="content",
        ),
        ContractSection(
            order=1,
            heading="First section",
            heading_level=2,
            content="First contractual condition.",
            source_area="content",
        ),
    ]

    monkeypatch.setattr(
        preprocessor_agent,
        "parse_contract_html",
        lambda raw_html: (
            "Terms",
            "en",
            sections,
        ),
    )

    response = run_preprocessor_agent(contract)

    assert response.status == "error"
    assert response.result is None
    assert response.error is not None
    assert "orden original ascendente" in response.error

def test_preprocessor_splits_oversized_html_block() -> None:
    """Ninguna clausula final debe superar el limite configurado."""

    sentence = (
        "The subscriber must comply with all contractual "
        "conditions established for the service. "
    )

    long_text = sentence * 70

    assert len(long_text) > preprocessor_agent.MAX_CHUNK_CHARS

    contract = create_contract(

            "<html lang=\"en\">"
            "<head><title>Terms</title></head>"
            "<body><main>"
            "<h2>Service Conditions</h2>"
            f"<p>{long_text}</p>"
            "</main></body>"
            "</html>"

    )

    response = run_preprocessor_agent(
        contract
    )

    assert response.status == "success"
    assert response.result is not None
    assert len(response.result.clauses) >= 2

    assert all(
        len(clause.content)
        <= preprocessor_agent.MAX_CHUNK_CHARS
        for clause in response.result.clauses
    )
