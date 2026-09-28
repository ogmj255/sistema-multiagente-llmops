import pytest
from app.llm.models import ModelResponse
from app.schemas.knowledge import LegalKnowledgeMatch
from app.schemas.legal_analysis import (
    ClauseAnalysisDecision,
    ClauseAnalysisRequest,
)
from app.schemas.preprocessing import ProcessedClause
from app.services.analysis import (
    ClassificationExecution,
    LegalGroundingError,
    build_grounded_assessment,
)


def create_request() -> ClauseAnalysisRequest:
    """Crea la cláusula original analizada."""

    return ClauseAnalysisRequest(
        source_url="https://example.com/terms",
        platform="Example SaaS",
        language="es",
        clause=ProcessedClause(
            order=1,
            original_order=4,
            heading="Modificación unilateral",
            heading_level=2,
            content="El proveedor podrá modificar el precio.",
        ),
    )


def create_match(
    document_id: str,
    chunk_index: int,
    distance: float,
) -> LegalKnowledgeMatch:
    """Crea una evidencia jurídica identificable."""

    return LegalKnowledgeMatch(
        chunk_id=f"{document_id}_chunk_{chunk_index:04d}",
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
        category="Modificación de condiciones",
        clause_type="Facultad unilateral del proveedor",
        target="Proveedor",
        consequence="El precio puede cambiar para el usuario.",
        classification="strong_indications_of_abusiveness",
        analysis_status="classified",
        justification=(
            "La cláusula presenta indicios fuertes "
            "de modificación unilateral."
        ),
        recommendation="Revisar la facultad de modificación.",
        evidence_sufficiency="sufficient",
        legal_basis_indices=indices,
    )

    return ClassificationExecution(
        decision=decision,
        model_response=ModelResponse(
            provider="openrouter",
            model="deepseek/deepseek-v4-flash-0731",
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
        create_request(),
        [first_match, second_match],
    )

    assert assessment.classification == (
        "strong_indications_of_abusiveness"
    )
    assert assessment.category == "Modificación de condiciones"
    assert assessment.clause_type == (
        "Facultad unilateral del proveedor"
    )
    assert assessment.target == "Proveedor"
    assert assessment.consequence == (
        "El precio puede cambiar para el usuario."
    )
    assert assessment.legal_basis == [second_match]
    assert assessment.relevant_fragment == (
        create_request().clause.content
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
        create_request(),
        [match],
    )

    basis = assessment.legal_basis[0]

    assert basis.chunk_id == "ec_consumer_law_chunk_0048"
    assert str(basis.source_url) == "https://example.com/law"
    assert basis.distance == 0.18


def test_builds_classification_without_legal_basis() -> None:
    """Conserva la clasificación con evidencia insuficiente."""

    decision = ClauseAnalysisDecision(
        category="Modificación de condiciones",
        clause_type="Facultad unilateral del proveedor",
        target="Proveedor",
        consequence="El precio puede cambiar para el usuario.",
        classification="potentially_abusive",
        analysis_status="classified",
        justification=(
            "El fragmento presenta indicios de desequilibrio, "
            "pero la evidencia recuperada es insuficiente."
        ),
        recommendation="Revisar jurídicamente la disposición.",
        evidence_sufficiency="insufficient",
        legal_basis_indices=[],
    )

    execution = ClassificationExecution(
        decision=decision,
        model_response=ModelResponse(
            provider="openrouter",
            model="deepseek/deepseek-v4-flash-0731",
            content="{}",
        ),
    )

    assessment = build_grounded_assessment(
        execution,
        create_request(),
        [],
    )

    assert assessment.analysis_status == "classified"
    assert assessment.classification == "potentially_abusive"
    assert assessment.evidence_sufficiency == "insufficient"
    assert assessment.legal_basis == []


def test_builds_not_applicable_assessment() -> None:
    """Permite excluir un fragmento sin disposición contractual."""

    decision = ClauseAnalysisDecision(
        category="Encabezado contractual",
        clause_type="Título sin contenido normativo",
        target="No aplica",
        consequence=None,
        classification=None,
        analysis_status="not_applicable",
        justification=(
            "El fragmento corresponde únicamente a un encabezado."
        ),
        recommendation=None,
        evidence_sufficiency="insufficient",
        legal_basis_indices=[],
    )

    execution = ClassificationExecution(
        decision=decision,
        model_response=ModelResponse(
            provider="openrouter",
            model="deepseek/deepseek-v4-flash-0731",
            content="{}",
        ),
    )

    assessment = build_grounded_assessment(
        execution,
        create_request(),
        [],
    )

    assert assessment.analysis_status == "not_applicable"
    assert assessment.classification is None
    assert assessment.legal_basis == []


def test_rejects_unknown_legal_basis() -> None:
    """Controla una referencia jurídica inexistente."""

    with pytest.raises(
        LegalGroundingError,
        match="inexistente",
    ):
        build_grounded_assessment(
            create_execution([1]),
            create_request(),
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
            create_request(),
            [
                create_match(
                    "ec_consumer_law",
                    48,
                    0.18,
                )
            ],
        )
