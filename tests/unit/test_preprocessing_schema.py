import pytest
from app.schemas.preprocessing import (
    PreprocessedContract,
    PreprocessingResponse,
    ProcessedClause,
    RemovedBlock,
)
from pydantic import ValidationError


def test_create_preprocessed_contract() -> None:
    """Comprueba la creación de un contrato preprocesado."""

    clause = ProcessedClause(
        order=1,
        original_order=5,
        heading="Account Terms",
        content="The user must provide accurate information.",
    )

    removed_block = RemovedBlock(
        original_order=1,
        content="Contact Sales",
        reason="Contenido de navegación.",
    )

    contract = PreprocessedContract(
        source_url="https://example.com/terms",
        platform="Example",
        title="Terms of Service",
        language="en",
        cleaned_text=clause.content,
        clauses=[clause],
        removed_blocks=[removed_block],
    )

    response = PreprocessingResponse(
        status="success",
        result=contract,
    )

    assert response.status == "success"
    assert response.result is not None
    assert len(response.result.clauses) == 1
    assert len(response.result.removed_blocks) == 1
    assert response.result.clauses[0].original_order == 5


def test_reject_clause_with_invalid_order() -> None:
    """Comprueba que el orden de una cláusula sea válido."""

    with pytest.raises(ValidationError):
        ProcessedClause(
            order=0,
            original_order=1,
            heading="Condiciones",
            content="Contenido contractual de prueba.",
        )
