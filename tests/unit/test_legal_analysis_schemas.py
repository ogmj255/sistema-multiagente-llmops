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


def test_analysis_request_uses_processed_clause() -> None:
    """Reutiliza la salida del preprocesador."""

    request = ClauseAnalysisRequest(
        source_url="https://example.com/terms",
        platform="Example SaaS",
        language="es",
        clause=create_clause(),
    )

    assert request.clause.original_order == 5


def test_analysis_request_rejects_unknown_jurisdiction() -> None:
    """Rechaza campos obsoletos en la solicitud de análisis."""

    with pytest.raises(ValidationError) as exc_info:
        ClauseAnalysisRequest(
            source_url="https://example.com/terms",
            platform="Example SaaS",
            language="es",
            clause=create_clause(),
            jurisdiction="ecuador",
        )

    errors = exc_info.value.errors()

    assert len(errors) == 1
    assert errors[0]["type"] == "extra_forbidden"
    assert errors[0]["loc"] == ("jurisdiction",)


def test_classified_clause_accepts_free_descriptions() -> None:
    """Acepta descripciones contractuales generadas por el LLM."""

    assessment = ClauseAssessment(
        category="Responsabilidad por daños",
        clause_type="Limitación de responsabilidad del proveedor",
        target="Proveedor",
        consequence=(
            "El usuario podría asumir daños que el proveedor excluye."
        ),
        classification="not_potentially_abusive",
        analysis_status="classified",
        relevant_fragment=create_clause().content,
        justification=(
            "La disposición conserva los derechos legales del usuario."
        ),
        recommendation="No se requieren acciones adicionales.",
        evidence_sufficiency="sufficient",
        legal_basis=[create_legal_basis()],
    )

    assert assessment.category == "Responsabilidad por daños"
    assert assessment.clause_type == (
        "Limitación de responsabilidad del proveedor"
    )
    assert assessment.target == "Proveedor"


def test_strong_indications_require_human_review() -> None:
    """Marca revisión humana cuando existen indicios fuertes."""

    assessment = ClauseAssessment(
        category="Responsabilidad contractual",
        clause_type="Exclusión amplia de responsabilidad",
        target="Proveedor",
        consequence="El proveedor excluye responsabilidad por daños.",
        classification="strong_indications_of_abusiveness",
        analysis_status="classified",
        relevant_fragment=create_clause().content,
        justification=(
            "La exclusión presenta indicios claros de desequilibrio."
        ),
        recommendation="Revisar jurídicamente la disposición.",
        evidence_sufficiency="sufficient",
        legal_basis=[create_legal_basis()],
    )

    assert assessment.classification == (
        "strong_indications_of_abusiveness"
    )


def test_insufficient_evidence_does_not_block_classification() -> None:
    """Permite clasificar aunque el RAG sea insuficiente."""

    assessment = ClauseAssessment(
        category="Responsabilidad contractual",
        clause_type="Exclusión de responsabilidad",
        target="Proveedor",
        consequence="El usuario asume posibles daños.",
        classification="potentially_abusive",
        analysis_status="classified",
        relevant_fragment=create_clause().content,
        justification=(
            "El contenido presenta indicios de desequilibrio, "
            "pero no existe respaldo jurídico suficiente "
            "en la evidencia recuperada."
        ),
        recommendation="Revisar la disposición jurídicamente.",
        evidence_sufficiency="insufficient",
        legal_basis=[],
    )

    assert assessment.classification == "potentially_abusive"
    assert assessment.evidence_sufficiency == "insufficient"
    assert assessment.legal_basis == []


def test_partial_evidence_requires_legal_basis() -> None:
    """Exige fundamento cuando se declara evidencia parcial."""

    with pytest.raises(
        ValidationError,
        match="fundamento jurídico",
    ):
        ClauseAssessment(
            category="Responsabilidad contractual",
            clause_type="Limitación de responsabilidad",
            target="Proveedor",
            consequence=None,
            classification="potentially_abusive",
            analysis_status="classified",
            relevant_fragment=create_clause().content,
            justification="Existen indicios de posible desequilibrio.",
            recommendation="Revisar la disposición.",
            evidence_sufficiency="partial",
            legal_basis=[],
        )


def test_not_applicable_fragment_has_no_classification() -> None:
    """Permite excluir un fragmento sin contenido contractual."""

    assessment = ClauseAssessment(
        category="Encabezado contractual",
        clause_type="Título sin contenido normativo",
        target="No aplica",
        consequence=None,
        classification=None,
        analysis_status="not_applicable",
        relevant_fragment="Limitación de responsabilidad",
        justification=(
            "El fragmento corresponde únicamente a un encabezado."
        ),
        recommendation=None,
        evidence_sufficiency="insufficient",
        legal_basis=[],
    )

    assert assessment.classification is None
    assert assessment.analysis_status == "not_applicable"
