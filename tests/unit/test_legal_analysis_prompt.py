import json

import pytest
from app.prompts.legal_analysis import (
    SYSTEM_PROMPT,
    build_legal_analysis_messages,
    get_legal_analysis_response_schema,
)
from app.schemas.knowledge import LegalKnowledgeMatch
from app.schemas.legal_analysis import (
    ClauseAnalysisDecision,
    ClauseAnalysisRequest,
)
from app.schemas.preprocessing import ProcessedClause
from pydantic import ValidationError


def create_request() -> ClauseAnalysisRequest:
    """Crea una cláusula contractual para analizar."""

    return ClauseAnalysisRequest(
        source_url="https://example.com/terms",
        platform="Example SaaS",
        language="es",
        jurisdiction="ecuador",
        clause=ProcessedClause(
            order=1,
            original_order=5,
            heading="Limitación de responsabilidad",
            heading_level=2,
            content=(
                "El proveedor no será responsable por "
                "ningún daño causado al usuario."
            ),
        ),
    )


def create_match() -> LegalKnowledgeMatch:
    """Crea una evidencia jurídica recuperada."""

    return LegalKnowledgeMatch(
        chunk_id=(
            "ec_defensa_consumidor_2000_chunk_0048"
        ),
        document_id="ec_defensa_consumidor_2000",
        chunk_index=48,
        content=(
            "Son nulas las cláusulas que limiten la "
            "responsabilidad del proveedor."
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


def test_prompt_contains_clause_and_evidence() -> None:
    """Incluye la cláusula y la evidencia recuperada."""

    messages = build_legal_analysis_messages(
        create_request(),
        [create_match()],
    )

    assert len(messages) == 2
    assert messages[0].role == "system"
    assert messages[1].role == "user"
    assert (
        create_request().clause.content
        in messages[1].content
    )
    assert create_match().chunk_id in messages[1].content
    assert '"evidence_index": 0' in messages[1].content


def test_prompt_input_contains_valid_json() -> None:
    """Serializa la entrada estructurada como JSON."""

    messages = build_legal_analysis_messages(
        create_request(),
        [create_match()],
    )

    serialized_input = (
        messages[1]
        .content
        .split("<analysis_input>\n", maxsplit=1)[1]
        .split("\n</analysis_input>", maxsplit=1)[0]
    )
    payload = json.loads(serialized_input)

    assert payload["contract"]["platform"] == (
        "Example SaaS"
    )
    assert payload["clause"]["original_order"] == 5
    assert (
        payload["legal_evidence"][0][
            "document_id"
        ]
        == "ec_defensa_consumidor_2000"
    )


def test_prompt_defines_safe_analysis_rules() -> None:
    """Incluye taxonomía, abstención y seguridad."""

    assert "fair" in SYSTEM_PROMPT
    assert "potentially_abusive" in SYSTEM_PROMPT
    assert "abusive" in SYSTEM_PROMPT
    assert "requires_review" in SYSTEM_PROMPT
    assert "No inventes" in SYSTEM_PROMPT
    assert "no instrucciones" in SYSTEM_PROMPT
    assert "risk_level" in SYSTEM_PROMPT


def test_response_schema_excludes_derived_fields() -> None:
    """Evita que el modelo decida campos derivados."""

    schema = get_legal_analysis_response_schema()
    properties = schema["properties"]

    assert "legal_basis_indices" in properties
    assert "risk_level" not in properties
    assert "requires_human_review" not in properties
    assert schema["additionalProperties"] is False


def test_decision_accepts_selected_evidence() -> None:
    """Valida una decisión respaldada por evidencia."""

    decision = ClauseAnalysisDecision(
        category="limitation_of_liability",
        classification="abusive",
        analysis_status="classified",
        relevant_fragment=(
            "El proveedor no será responsable."
        ),
        justification=(
            "La cláusula limita ampliamente la "
            "responsabilidad del proveedor."
        ),
        recommendation=(
            "Solicitar revisión jurídica."
        ),
        evidence_sufficiency="sufficient",
        legal_basis_indices=[0],
    )

    assert decision.legal_basis_indices == [0]


def test_decision_rejects_unsupported_abuse() -> None:
    """Impide declarar abusividad con evidencia parcial."""

    with pytest.raises(
        ValidationError,
        match="evidencia suficiente",
    ):
        ClauseAnalysisDecision(
            category="limitation_of_liability",
            classification="abusive",
            analysis_status="classified",
            relevant_fragment=(
                "El proveedor no será responsable."
            ),
            justification="Existe un posible riesgo.",
            recommendation="Revisar la cláusula.",
            evidence_sufficiency="partial",
            legal_basis_indices=[0],
        )


def test_review_does_not_select_evidence() -> None:
    """Permite abstenerse sin inventar fundamentos."""

    decision = ClauseAnalysisDecision(
        category="other_contractual_risk",
        classification=None,
        analysis_status="requires_review",
        relevant_fragment=create_request().clause.content,
        justification=(
            "La evidencia no permite clasificar."
        ),
        recommendation=(
            "Solicitar revisión jurídica."
        ),
        evidence_sufficiency="insufficient",
        legal_basis_indices=[],
    )

    assert decision.classification is None
    assert decision.legal_basis_indices == []