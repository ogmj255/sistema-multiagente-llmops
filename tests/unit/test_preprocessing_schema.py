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
def test_serialize_preprocessing_response_to_json() -> None:
    """Comprueba la serialización y reconstrucción de la salida JSON."""

    clause = ProcessedClause(
        order=1,
        original_order=5,
        heading="Account Terms",
        heading_level=2,
        content="The user must protect the account.",
    )

    contract = PreprocessedContract(
        source_url="https://example.com/terms",
        platform="Example",
        title="Terms of Service",
        language="en",
        cleaned_text=clause.content,
        clauses=[clause],
        removed_blocks=[],
    )

    response = PreprocessingResponse(
        status="success",
        result=contract,
    )

    serialized = response.model_dump_json()
    restored = PreprocessingResponse.model_validate_json(
        serialized
    )

    assert restored.status == "success"
    assert restored.result is not None
    assert restored.result.platform == "Example"
    assert restored.result.clauses[0].order == 1
    assert restored.result.clauses[0].original_order == 5
    assert restored.result.clauses[0].heading_level == 2
    assert restored.error is None


def test_reject_success_response_without_result() -> None:
    """Rechaza una respuesta exitosa que no contiene resultado."""

    with pytest.raises(
        ValidationError,
        match="respuesta exitosa debe contener un resultado",
    ):
        PreprocessingResponse(status="success")


def test_reject_error_response_without_message() -> None:
    """Rechaza una respuesta de error sin mensaje explicativo."""

    with pytest.raises(
        ValidationError,
        match="respuesta de error debe contener un mensaje",
    ):
        PreprocessingResponse(status="error")


def test_reject_preprocessed_contract_without_clauses() -> None:
    """Rechaza un contrato preprocesado sin cláusulas."""

    with pytest.raises(ValidationError):
        PreprocessedContract(
            source_url="https://example.com/terms",
            platform="Example",
            title="Terms of Service",
            language="en",
            cleaned_text="Contractual content.",
            clauses=[],
            removed_blocks=[],
        )