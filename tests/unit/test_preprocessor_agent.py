from datetime import UTC, datetime

from app.agents.preprocessor_agent import (
    run_preprocessor_agent,
)
from app.schemas.contract import (
    ContractSection,
    ExtractedContract,
)


def create_contract(
    sections: list[ContractSection],
) -> ExtractedContract:
    """Crea un contrato para probar el agente."""

    return ExtractedContract(
        source_url="https://example.com/terms",
        platform="Example",
        title="Terms of Service",
        retrieved_at=datetime.now(UTC),
        extraction_method="beautiful_soup",
        language="en",
        sections=sections,
        full_text="\n\n".join(
            section.content for section in sections
        ),
    )


def test_preprocessor_cleans_and_segments_contract() -> None:
    """Comprueba el pipeline completo del preprocesador."""

    contract = create_contract(
        [
            ContractSection(
                order=1,
                content="Products and services",
                html_tag="li",
                source_area="navigation",
                is_link_only=True,
            ),
            ContractSection(
                order=2,
                heading="Account Terms",
                content="The user must provide accurate information.",
                html_tag="p",
                source_area="content",
            ),
            ContractSection(
                order=3,
                heading="Account Terms",
                content="The user must protect the account.",
                html_tag="li",
                source_area="content",
            ),
            ContractSection(
                order=4,
                content="Company information",
                html_tag="li",
                source_area="footer",
                is_link_only=True,
            ),
        ]
    )

    response = run_preprocessor_agent(contract)

    assert response.status == "success"
    assert response.result is not None
    assert len(response.result.clauses) == 2
    assert len(response.result.removed_blocks) == 2
    assert response.result.clauses[0].original_order == 2
    assert response.result.clauses[1].original_order == 3
    assert response.result.cleaned_text.count(
        "Account Terms"
    ) == 1


def test_preprocessor_preserves_logical_order() -> None:
    """Comprueba que las cláusulas mantengan el orden original."""

    contract = create_contract(
        [
            ContractSection(
                order=4,
                heading="First section",
                content="First contractual condition.",
                source_area="content",
            ),
            ContractSection(
                order=8,
                heading="Second section",
                content="Second contractual condition.",
                source_area="content",
            ),
        ]
    )

    response = run_preprocessor_agent(contract)

    assert response.result is not None
    assert response.result.clauses[0].original_order == 4
    assert response.result.clauses[1].original_order == 8
    assert response.result.clauses[0].order == 1
    assert response.result.clauses[1].order == 2


def test_preprocessor_returns_error_without_contract_content() -> None:
    """Comprueba la respuesta cuando todo el contenido es ruido."""

    contract = create_contract(
        [
            ContractSection(
                order=1,
                content="Navigation option",
                source_area="navigation",
                is_link_only=True,
            ),
            ContractSection(
                order=2,
                content="Footer option",
                source_area="footer",
                is_link_only=True,
            ),
        ]
    )

    response = run_preprocessor_agent(contract)

    assert response.status == "error"
    assert response.result is None
    assert response.error is not None
    assert "No se encontró contenido contractual" in response.error

def test_preprocessor_controls_inconsistent_section_order() -> None:
    """Devuelve un error controlado cuando el orden es inconsistente."""

    contract = create_contract(
        [
            ContractSection(
                order=2,
                heading="Second section",
                content="Second contractual condition.",
                source_area="content",
            ),
            ContractSection(
                order=1,
                heading="First section",
                content="First contractual condition.",
                source_area="content",
            ),
        ]
    )

    response = run_preprocessor_agent(contract)

    assert response.status == "error"
    assert response.result is None
    assert response.error is not None
    assert "orden original ascendente" in response.error