"""Regresión V2.1: reglas del prompt y validez estructural sin usar API."""

import pytest
from pydantic import ValidationError

from app.prompts.legal_analysis import (
    ANALYSIS_GUIDANCE,
    CLASSIFICATION_GUIDANCE,
    SYSTEM_PROMPT,
    get_legal_analysis_response_schema,
)
from app.schemas.legal_analysis import ClauseAnalysisDecision


def _valid_decision() -> dict:
    return {
        "category": "Condiciones de uso",
        "clause_type": "Obligación contractual",
        "target": "Usuario",
        "consequence": None,
        "classification": "not_potentially_abusive",
        "analysis_status": "classified",
        "justification": "El texto disponible no presenta indicios suficientes.",
        "recommendation": "Revisar el contexto contractual.",
        "evidence_sufficiency": "insufficient",
        "legal_basis_indices": [],
    }


def test_v21_consequence_is_explicit_not_hypothetical():
    assert "conste explícitamente" in ANALYSIS_GUIDANCE
    assert "no establece ninguna" in ANALYSIS_GUIDANCE
    assert "directamente derivable" not in SYSTEM_PROMPT


def test_v21_habituality_not_used_as_default_negative():
    assert "habitualidad de una disposición no determina" in SYSTEM_PROMPT
    assert "ni motivo" in SYSTEM_PROMPT


def test_v21_truncated_unit_requires_textual_indication():
    assert "No reconstruyas contenido truncado" in CLASSIFICATION_GUIDANCE
    assert "al menos un indicio concreto" in CLASSIFICATION_GUIDANCE
    assert "no garantiza ausencia de riesgos" in CLASSIFICATION_GUIDANCE


def test_v21_mixed_unit_single_label_and_explicit_exception():
    assert "una sola clasificación al conjunto" in CLASSIFICATION_GUIDANCE
    assert "excepciones y protecciones" in CLASSIFICATION_GUIDANCE
    assert "no neutralizan automáticamente" in CLASSIFICATION_GUIDANCE


def test_v21_rag_evidence_is_distinct_from_risk_and_linguistic_output():
    assert "NO la confianza de la clasificación" in CLASSIFICATION_GUIDANCE
    assert "- sufficient:" in CLASSIFICATION_GUIDANCE
    assert "- partial:" in CLASSIFICATION_GUIDANCE
    assert "- insufficient:" in CLASSIFICATION_GUIDANCE
    assert "en español" in SYSTEM_PROMPT
    assert "códigos enumerados" in SYSTEM_PROMPT


def test_v21_rejects_strict_extra_without_mutating_schema():
    data = _valid_decision()
    decision = ClauseAnalysisDecision.model_validate(data)
    assert decision.classification == "not_potentially_abusive"
    assert get_legal_analysis_response_schema()["additionalProperties"] is False
    with pytest.raises(ValidationError) as err:
        ClauseAnalysisDecision.model_validate({**data, "strict": True})
    assert any(
        row["type"] == "extra_forbidden" and row["loc"] == ("strict",)
        for row in err.value.errors()
    )


def test_v21_not_applicable_remains_separate_state():
    decision = _valid_decision()
    decision["classification"] = None
    decision["analysis_status"] = "not_applicable"
    assert ClauseAnalysisDecision.model_validate(decision).classification is None
    with pytest.raises(ValidationError):
        ClauseAnalysisDecision.model_validate({
            **decision, "classification": "potentially_abusive",
        })
