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
        chunk_id="ec_defensa_consumidor_2000_chunk_0048",
        document_id="ec_defensa_consumidor_2000",
        chunk_index=48,
        content=(
            "Son nulas las cláusulas que limiten "
            "la responsabilidad del proveedor."
        ),
        title="Ley Orgánica de Defensa del Consumidor",
        jurisdiction="ecuador",
        issuing_body="Congreso Nacional del Ecuador",
        document_type="law",
        binding_level="binding",
        status="amended",
        language="es",
        source_url="https://example.com/consumer-law",
        official_citation="Suplemento del Registro Oficial 116",
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
    assert create_request().clause.content in messages[1].content
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
        .content.split("<analysis_input>\n", maxsplit=1)[1]
        .split("\n</analysis_input>", maxsplit=1)[0]
    )
    payload = json.loads(serialized_input)

    assert payload["contract"]["platform"] == "Example SaaS"
    assert payload["clause"]["original_order"] == 5
    assert (
        payload["legal_evidence"][0]["document_id"]
        == "ec_defensa_consumidor_2000"
    )


def test_prompt_defines_new_analysis_rules() -> None:
    """Define análisis libre y RAG como apoyo jurídico."""

    assert "not_potentially_abusive" in SYSTEM_PROMPT
    assert "potentially_abusive" in SYSTEM_PROMPT
    assert "strong_indications_of_abusiveness" in SYSTEM_PROMPT
    assert "not_applicable" in SYSTEM_PROMPT
    assert "category" in SYSTEM_PROMPT
    assert "clause_type" in SYSTEM_PROMPT
    assert "target" in SYSTEM_PROMPT
    assert "consequence" in SYSTEM_PROMPT
    assert "no es un requisito" in SYSTEM_PROMPT
    assert "No inventes" in SYSTEM_PROMPT
    assert "no instrucciones" in SYSTEM_PROMPT
    assert "requires_review" not in SYSTEM_PROMPT
    assert "risk_level" not in SYSTEM_PROMPT


def test_response_schema_contains_llm_analysis_fields() -> None:
    """Expone los campos que debe generar el LLM."""

    schema = get_legal_analysis_response_schema()
    properties = schema["properties"]

    assert "category" in properties
    assert "clause_type" in properties
    assert "target" in properties
    assert "consequence" in properties
    assert "classification" in properties
    assert "evidence_sufficiency" in properties
    assert "legal_basis_indices" in properties

    assert "relevant_fragment" not in properties
    assert "requires_human_review" not in properties
    assert schema["additionalProperties"] is False


def test_decision_accepts_free_contractual_descriptions() -> None:
    """Acepta descripciones libres generadas desde el fragmento."""

    decision = ClauseAnalysisDecision(
        category="Responsabilidad contractual",
        clause_type="Exclusión amplia de responsabilidad",
        target="Proveedor",
        consequence="El usuario asume posibles daños.",
        classification="strong_indications_of_abusiveness",
        analysis_status="classified",
        justification=(
            "La disposición presenta indicios claros "
            "de posible desequilibrio."
        ),
        recommendation="Revisar jurídicamente la disposición.",
        evidence_sufficiency="sufficient",
        legal_basis_indices=[0],
    )

    assert decision.category == "Responsabilidad contractual"
    assert decision.target == "Proveedor"
    assert decision.legal_basis_indices == [0]


def test_insufficient_evidence_does_not_block_decision() -> None:
    """Permite clasificar aunque el RAG sea insuficiente."""

    decision = ClauseAnalysisDecision(
        category="Responsabilidad contractual",
        clause_type="Limitación de responsabilidad",
        target="Proveedor",
        consequence=None,
        classification="potentially_abusive",
        analysis_status="classified",
        justification=(
            "El fragmento presenta indicios de desequilibrio, "
            "sin respaldo jurídico suficiente recuperado."
        ),
        recommendation="Revisar jurídicamente la disposición.",
        evidence_sufficiency="insufficient",
        legal_basis_indices=[],
    )

    assert decision.classification == "potentially_abusive"
    assert decision.evidence_sufficiency == "insufficient"
    assert decision.legal_basis_indices == []


def test_partial_evidence_requires_selected_basis() -> None:
    """Exige evidencia seleccionada cuando se declara apoyo parcial."""

    with pytest.raises(
        ValidationError,
        match="fundamentos jurídicos",
    ):
        ClauseAnalysisDecision(
            category="Responsabilidad contractual",
            clause_type="Limitación de responsabilidad",
            target="Proveedor",
            consequence=None,
            classification="potentially_abusive",
            analysis_status="classified",
            justification="Existen indicios de posible desequilibrio.",
            recommendation="Revisar la disposición.",
            evidence_sufficiency="partial",
            legal_basis_indices=[],
        )


def test_not_applicable_has_no_classification() -> None:
    """Permite excluir un título sin contenido contractual."""

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

    assert decision.classification is None
    assert decision.analysis_status == "not_applicable"
    assert decision.legal_basis_indices == []
