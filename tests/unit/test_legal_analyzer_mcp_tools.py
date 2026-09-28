import pytest

from app.agents.legal_analyzer_agent import LegalAnalyzerExecution
from app.mcp import legal_analyzer_tools
from app.schemas.knowledge import LegalKnowledgeMatch
from app.schemas.legal_analysis import (
    ClauseAnalysisRequest,
    ClauseAnalysisResponse,
    ClauseAssessment,
)
from app.schemas.observability import LLMInvocationMetrics
from app.schemas.preprocessing import ProcessedClause


def create_clause() -> ProcessedClause:
    """Crea una cláusula procesada para el MCP."""

    return ProcessedClause(
        order=1,
        original_order=4,
        heading="Modificación unilateral",
        heading_level=2,
        content=(
            "El proveedor podrá modificar "
            "unilateralmente el precio del servicio."
        ),
    )


def create_match() -> LegalKnowledgeMatch:
    """Crea un fundamento jurídico para la prueba."""

    return LegalKnowledgeMatch(
        chunk_id="ec_defensa_consumidor_2000_chunk_0048",
        document_id="ec_defensa_consumidor_2000",
        chunk_index=48,
        content=(
            "Son nulas las cláusulas que permiten al "
            "proveedor variar unilateralmente el precio."
        ),
        title="Ley Orgánica de Defensa del Consumidor",
        jurisdiction="ecuador",
        issuing_body="Congreso Nacional del Ecuador",
        document_type="law",
        binding_level="binding",
        status="amended",
        language="es",
        source_url="https://example.com/consumer-law",
        official_citation="Registro Oficial 116",
        topics="consumidores|contratos",
        checksum="a" * 64,
        distance=0.18,
    )


def create_assessment(
    *,
    evidence_sufficiency: str = "sufficient",
    legal_basis: list[LegalKnowledgeMatch] | None = None,
) -> ClauseAssessment:
    """Crea una valoración jurídica válida."""

    if legal_basis is None:
        legal_basis = (
            [create_match()]
            if evidence_sufficiency != "insufficient"
            else []
        )

    return ClauseAssessment(
        category="Modificación de condiciones",
        clause_type="Facultad unilateral del proveedor",
        target="Proveedor",
        consequence=(
            "El precio del servicio puede cambiar para el usuario."
        ),
        classification="strong_indications_of_abusiveness",
        analysis_status="classified",
        relevant_fragment=(
            "El proveedor podrá modificar "
            "unilateralmente el precio del servicio."
        ),
        justification=(
            "La cláusula presenta indicios fuertes "
            "de modificación unilateral."
        ),
        recommendation="Revisar la facultad unilateral.",
        evidence_sufficiency=evidence_sufficiency,
        legal_basis=legal_basis,
    )


def create_metrics() -> LLMInvocationMetrics:
    """Crea telemetría LLM realista para el contrato MCP."""

    return LLMInvocationMetrics(
        provider="openrouter",
        model="model-test",
        prompt_tokens=120,
        completion_tokens=30,
        total_tokens=150,
        cost_usd=0.0042,
    )


@pytest.mark.asyncio
async def test_analyze_legal_clause_tool(
    monkeypatch,
) -> None:
    """Comprueba análisis y telemetría devueltos por MCP."""

    clause = create_clause()
    legal_context = [create_match()]

    def fake_agent(
        request: ClauseAnalysisRequest,
        received_context: list[LegalKnowledgeMatch],
    ) -> LegalAnalyzerExecution:
        assert str(request.source_url) == "https://example.com/terms"
        assert request.platform == "Example SaaS"
        assert request.language == "es"
        assert request.clause == clause
        assert received_context == legal_context

        return LegalAnalyzerExecution(
            response=ClauseAnalysisResponse(
                status="success",
                result=create_assessment(),
            ),
            llm_metrics=create_metrics(),
        )

    monkeypatch.setattr(
        legal_analyzer_tools,
        "run_legal_analyzer_execution_with_context",
        fake_agent,
    )

    result = await legal_analyzer_tools.analyze_legal_clause(
        source_url="https://example.com/terms",
        platform="Example SaaS",
        language="es",
        clause=clause,
        legal_context=legal_context,
    )

    analysis = result["analysis"]
    observability = result["observability"]

    assert analysis["status"] == "success"
    assert analysis["error"] is None
    assert analysis["result"] is not None
    assert analysis["result"]["classification"] == (
        "strong_indications_of_abusiveness"
    )
    assert analysis["result"]["category"] == (
        "Modificación de condiciones"
    )
    assert analysis["result"]["clause_type"] == (
        "Facultad unilateral del proveedor"
    )
    assert analysis["result"]["target"] == "Proveedor"
    assert len(analysis["result"]["legal_basis"]) == 1

    assert observability is not None
    assert observability["provider"] == "openrouter"
    assert observability["model"] == "model-test"
    assert observability["prompt_tokens"] == 120
    assert observability["completion_tokens"] == 30
    assert observability["total_tokens"] == 150
    assert observability["cost_usd"] == 0.0042


@pytest.mark.asyncio
async def test_analyzer_tool_accepts_empty_legal_context(
    monkeypatch,
) -> None:
    """Permite analizar aunque el RAG no entregue evidencias."""

    clause = create_clause()

    def fake_agent(
        request: ClauseAnalysisRequest,
        received_context: list[LegalKnowledgeMatch],
    ) -> LegalAnalyzerExecution:
        assert request.clause == clause
        assert received_context == []

        return LegalAnalyzerExecution(
            response=ClauseAnalysisResponse(
                status="success",
                result=create_assessment(
                    evidence_sufficiency="insufficient",
                    legal_basis=[],
                ),
            ),
            llm_metrics=create_metrics(),
        )

    monkeypatch.setattr(
        legal_analyzer_tools,
        "run_legal_analyzer_execution_with_context",
        fake_agent,
    )

    result = await legal_analyzer_tools.analyze_legal_clause(
        source_url="https://example.com/terms",
        platform="Example SaaS",
        language="es",
        clause=clause,
        legal_context=[],
    )

    analysis = result["analysis"]

    assert analysis["status"] == "success"
    assert analysis["error"] is None
    assert analysis["result"] is not None
    assert analysis["result"]["classification"] == (
        "strong_indications_of_abusiveness"
    )
    assert (
        analysis["result"]["evidence_sufficiency"]
        == "insufficient"
    )
    assert analysis["result"]["legal_basis"] == []
    assert result["observability"] is not None


@pytest.mark.asyncio
async def test_analyzer_tool_preserves_agent_error(
    monkeypatch,
) -> None:
    """Devuelve el error controlado del analizador."""

    legal_context = [create_match()]

    def fake_agent(
        request: ClauseAnalysisRequest,
        received_context: list[LegalKnowledgeMatch],
    ) -> LegalAnalyzerExecution:
        assert request.clause == create_clause()
        assert received_context == legal_context

        return LegalAnalyzerExecution(
            response=ClauseAnalysisResponse(
                status="error",
                error="No se pudo clasificar la cláusula.",
            ),
            llm_metrics=None,
        )

    monkeypatch.setattr(
        legal_analyzer_tools,
        "run_legal_analyzer_execution_with_context",
        fake_agent,
    )

    result = await legal_analyzer_tools.analyze_legal_clause(
        source_url="https://example.com/terms",
        platform="Example SaaS",
        language="es",
        clause=create_clause(),
        legal_context=legal_context,
    )

    analysis = result["analysis"]

    assert analysis["status"] == "error"
    assert analysis["result"] is None
    assert analysis["error"] == (
        "No se pudo clasificar la cláusula."
    )
    assert result["observability"] is None
