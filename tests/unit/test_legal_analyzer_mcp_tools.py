import pytest
from app.mcp import legal_analyzer_tools
from app.schemas.knowledge import LegalKnowledgeMatch
from app.schemas.legal_analysis import (
    ClauseAnalysisRequest,
    ClauseAnalysisResponse,
    ClauseAssessment,
)
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
        chunk_id=(
            "ec_defensa_consumidor_2000_chunk_0048"
        ),
        document_id="ec_defensa_consumidor_2000",
        chunk_index=48,
        content=(
            "Son nulas las cláusulas que permiten al "
            "proveedor variar unilateralmente el precio."
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
        official_citation="Registro Oficial 116",
        topics="consumidores|contratos",
        checksum="a" * 64,
        distance=0.18,
    )


def create_assessment() -> ClauseAssessment:
    """Crea una valoración jurídica válida."""

    return ClauseAssessment(
        category="unilateral_modification",
        classification="abusive",
        analysis_status="classified",
        relevant_fragment=(
            "El proveedor podrá modificar "
            "unilateralmente el precio del servicio."
        ),
        justification=(
            "La modificación unilateral está prohibida "
            "por la normativa de consumo."
        ),
        recommendation=(
            "Eliminar la facultad unilateral."
        ),
        evidence_sufficiency="sufficient",
        legal_basis=[create_match()],
    )


@pytest.mark.asyncio
async def test_analyze_legal_clause_tool(
    monkeypatch,
) -> None:
    """Comprueba entrada, agente y salida MCP."""

    clause = create_clause()

    def fake_agent(
        request: ClauseAnalysisRequest,
    ) -> ClauseAnalysisResponse:
        assert str(request.source_url) == (
            "https://example.com/terms"
        )
        assert request.platform == "Example SaaS"
        assert request.language == "es"
        assert request.jurisdiction == "ecuador"
        assert request.clause == clause

        return ClauseAnalysisResponse(
            status="success",
            result=create_assessment(),
        )

    monkeypatch.setattr(
        legal_analyzer_tools,
        "run_legal_analyzer_agent",
        fake_agent,
    )

    result = await (
        legal_analyzer_tools.analyze_legal_clause(
            source_url="https://example.com/terms",
            platform="Example SaaS",
            language="es",
            jurisdiction="ecuador",
            clause=clause,
        )
    )

    assert result["status"] == "success"
    assert result["error"] is None
    assert result["result"] is not None
    assert (
        result["result"]["classification"]
        == "abusive"
    )
    assert result["result"]["risk_level"] == "high"
    assert len(result["result"]["legal_basis"]) == 1


@pytest.mark.asyncio
async def test_analyzer_tool_preserves_agent_error(
    monkeypatch,
) -> None:
    """Devuelve el error controlado del agente."""

    def fake_agent(
        request: ClauseAnalysisRequest,
    ) -> ClauseAnalysisResponse:
        return ClauseAnalysisResponse(
            status="error",
            error=(
                "No se pudo consultar la base jurídica."
            ),
        )

    monkeypatch.setattr(
        legal_analyzer_tools,
        "run_legal_analyzer_agent",
        fake_agent,
    )

    result = await (
        legal_analyzer_tools.analyze_legal_clause(
            source_url="https://example.com/terms",
            platform="Example SaaS",
            language="es",
            clause=create_clause(),
        )
    )

    assert result["status"] == "error"
    assert result["result"] is None
    assert result["error"] == (
        "No se pudo consultar la base jurídica."
    )