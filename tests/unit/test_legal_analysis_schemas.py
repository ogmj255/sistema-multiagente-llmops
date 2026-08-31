import pytest
from app.schemas.knowledge import LegalKnowledgeMatch
from app.schemas.legal_analysis import (
    ClauseAnalysisRequest,
    ClauseAssessment,
)
from app.schemas.preprocessing import ProcessedClause
from pydantic import ValidationError


def create_clause() -> ProcessedClause:
    """Crea una cláusula procesada para las pruebas."""

    return ProcessedClause(
        order=1,
        original_order=5,
        heading="Limitación de responsabilidad",
        heading_level=2,
        content=(
            "El proveedor no será responsable por "
            "ningún daño causado al usuario."
        ),
    )


def create_legal_basis() -> LegalKnowledgeMatch:
    """Crea un fundamento jurídico recuperado."""

    return LegalKnowledgeMatch(
        chunk_id=(
            "ec_defensa_consumidor_2000_chunk_0048"
        ),
        document_id="ec_defensa_consumidor_2000",
        chunk_index=48,
        content=(
            "Son nulas las cláusulas que limiten "
            "la responsabilidad del proveedor."
        ),
        title=(
            "Ley Orgánica de Defensa del Consumidor"
        ),
        jurisdiction="ecuador",
        issuing_body="Congreso Nacional del Ecuador",
        document_type="law",
        binding_level="binding",
        status="amended",
        language="es",
        source_url="https://example.com/consumer-law",
        official_citation=(
            "Suplemento del Registro Oficial 116"
        ),
        topics="consumidores|cláusulas abusivas",
        checksum="a" * 64,
        distance=0.18,
    )


def test_analysis_request_uses_processed_clause() -> None:
    """Reutiliza la salida del preprocesador."""

    request = ClauseAnalysisRequest(
        source_url="https://example.com/terms",
        platform="Example SaaS",
        language="es",
        clause=create_clause(),
    )

    assert request.jurisdiction == "ecuador"
    assert request.clause.original_order == 5


def test_fair_clause_derives_low_risk() -> None:
    """Deriva riesgo bajo para una cláusula justa."""

    assessment = ClauseAssessment(
        category="limitation_of_liability",
        classification="fair",
        analysis_status="classified",
        relevant_fragment=create_clause().content,
        justification=(
            "La limitación es proporcional y conserva "
            "los derechos legales del usuario."
        ),
        recommendation=(
            "No se requieren acciones adicionales."
        ),
        evidence_sufficiency="sufficient",
        legal_basis=[create_legal_basis()],
    )

    assert assessment.risk_level == "low"
    assert assessment.requires_human_review is False


def test_abusive_clause_derives_high_risk() -> None:
    """Deriva riesgo alto y revisión humana."""

    assessment = ClauseAssessment(
        category="limitation_of_liability",
        classification="abusive",
        analysis_status="classified",
        relevant_fragment=create_clause().content,
        justification=(
            "La cláusula excluye ampliamente la "
            "responsabilidad del proveedor."
        ),
        recommendation=(
            "Solicitar revisión jurídica especializada."
        ),
        evidence_sufficiency="sufficient",
        legal_basis=[create_legal_basis()],
    )

    assert assessment.risk_level == "high"
    assert assessment.requires_human_review is True


def test_abusive_clause_requires_sufficient_evidence() -> None:
    """Impide declarar abusividad con evidencia parcial."""

    with pytest.raises(
        ValidationError,
        match="evidencia jurídica suficiente",
    ):
        ClauseAssessment(
            category="limitation_of_liability",
            classification="abusive",
            analysis_status="classified",
            relevant_fragment=create_clause().content,
            justification="Existe un posible riesgo.",
            recommendation="Revisar la cláusula.",
            evidence_sufficiency="partial",
            legal_basis=[create_legal_basis()],
        )


def test_insufficient_evidence_requires_review() -> None:
    """Permite abstenerse cuando falta evidencia."""

    assessment = ClauseAssessment(
        category="other_contractual_risk",
        analysis_status="requires_review",
        relevant_fragment=create_clause().content,
        justification=(
            "La evidencia recuperada no permite "
            "realizar una clasificación."
        ),
        recommendation=(
            "Solicitar revisión jurídica especializada."
        ),
        evidence_sufficiency="insufficient",
    )

    assert assessment.classification is None
    assert assessment.risk_level is None
    assert assessment.requires_human_review is True


def test_rejects_inconsistent_risk_level() -> None:
    """Rechaza contradicciones entre clase y riesgo."""

    with pytest.raises(
        ValidationError,
        match="no corresponde",
    ):
        ClauseAssessment(
            category="unilateral_modification",
            classification="fair",
            risk_level="high",
            analysis_status="classified",
            relevant_fragment=create_clause().content,
            justification="No se identificaron indicios.",
            recommendation="No se requieren acciones.",
            evidence_sufficiency="sufficient",
            legal_basis=[create_legal_basis()],
        )