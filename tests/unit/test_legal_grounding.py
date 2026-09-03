import pytest
from app.llm.models import ModelResponse
from app.schemas.knowledge import LegalKnowledgeMatch
from app.schemas.legal_analysis import (
    ClauseAnalysisDecision,
)
from app.services.analysis import (
    ClassificationExecution,
    LegalGroundingError,
    build_grounded_assessment,
)


def create_match(
    document_id: str,
    chunk_index: int,
    distance: float,
) -> LegalKnowledgeMatch:
    """Crea una evidencia jurídica identificable."""

    return LegalKnowledgeMatch(
        chunk_id=(
            f"{document_id}_chunk_{chunk_index:04d}"
        ),
        document_id=document_id,
        chunk_index=chunk_index,
        content=(
            "Son nulas las cláusulas que permiten "
            "variaciones unilaterales del contrato."
        ),
        title="Normativa de protección al consumidor",
        jurisdiction="ecuador",
        issuing_body="Congreso Nacional del Ecuador",
        document_type="law",
        binding_level="binding",
        status="amended",
        language="es",
        source_url="https://example.com/law",
        official_citation="Registro Oficial 116",
        topics="consumidores|contratos",
        checksum="a" * 64,
        distance=distance,
    )


def create_execution(
    indices: list[int],
) -> ClassificationExecution:
    """Crea una clasificación generada por el modelo."""

    decision = ClauseAnalysisDecision(
        category="unilateral_modification",
        classification="abusive",
        analysis_status="classified",
        relevant_fragment=(
            "El proveedor podrá modificar el precio."
        ),
        justification=(
            "La cláusula permite una modificación "
            "unilateral prohibida por la normativa."
        ),
        recommendation=(
            "Eliminar la facultad unilateral."
        ),
        evidence_sufficiency="sufficient",
        legal_basis_indices=indices,
    )

    return ClassificationExecution(
        decision=decision,
        model_response=ModelResponse(
            provider="ollama",
            model="qwen3:4b",
            content="{}",
        ),
    )


def test_builds_assessment_with_selected_basis() -> None:
    """Relaciona los índices con evidencias exactas."""

    first_match = create_match(
        "ec_first_law",
        10,
        0.25,
    )
    second_match = create_match(
        "ec_second_law",
        20,
        0.18,
    )

    assessment = build_grounded_assessment(
        create_execution([1]),
        [first_match, second_match],
    )

    assert assessment.classification == "abusive"
    assert assessment.risk_level == "high"
    assert assessment.requires_human_review is True
    assert assessment.legal_basis == [second_match]
    assert (
        assessment.justification
        == create_execution([1]).decision.justification
    )


def test_preserves_exact_legal_metadata() -> None:
    """Conserva la fuente recuperada sin reconstruirla."""

    match = create_match(
        "ec_consumer_law",
        48,
        0.18,
    )

    assessment = build_grounded_assessment(
        create_execution([0]),
        [match],
    )

    basis = assessment.legal_basis[0]

    assert basis.chunk_id == (
        "ec_consumer_law_chunk_0048"
    )
    assert str(basis.source_url) == (
        "https://example.com/law"
    )
    assert basis.distance == 0.18


def test_builds_review_without_legal_basis() -> None:
    """Permite una abstención sin fuentes inventadas."""

    decision = ClauseAnalysisDecision(
        category="other_contractual_risk",
        classification=None,
        analysis_status="requires_review",
        relevant_fragment=(
            "El proveedor podrá modificar el precio."
        ),
        justification=(
            "La evidencia recuperada es insuficiente."
        ),
        recommendation=(
            "Solicitar revisión jurídica."
        ),
        evidence_sufficiency="insufficient",
        legal_basis_indices=[],
    )
    execution = ClassificationExecution(
        decision=decision,
        model_response=ModelResponse(
            provider="ollama",
            model="qwen3:4b",
            content="{}",
        ),
    )

    assessment = build_grounded_assessment(
        execution,
        [],
    )

    assert assessment.analysis_status == (
        "requires_review"
    )
    assert assessment.classification is None
    assert assessment.risk_level is None
    assert assessment.legal_basis == []


def test_rejects_unknown_legal_basis() -> None:
    """Controla una referencia jurídica inexistente."""

    with pytest.raises(
        LegalGroundingError,
        match="inexistente",
    ):
        build_grounded_assessment(
            create_execution([1]),
            [
                create_match(
                    "ec_consumer_law",
                    48,
                    0.18,
                )
            ],
        )


def test_rejects_duplicate_legal_basis() -> None:
    """Evita repetir una fuente jurídica."""

    with pytest.raises(
        LegalGroundingError,
        match="duplicados",
    ):
        build_grounded_assessment(
            create_execution([0, 0]),
            [
                create_match(
                    "ec_consumer_law",
                    48,
                    0.18,
                )
            ],
        )