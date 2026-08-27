import pytest
from app.mcp import knowledge_tools
from app.schemas.knowledge import (
    KnowledgeQuery,
    KnowledgeResponse,
    LegalKnowledgeMatch,
)


def create_match() -> LegalKnowledgeMatch:
    """Crea un resultado jurídico para la prueba MCP."""

    return LegalKnowledgeMatch(
        chunk_id="ec_test_law_chunk_0000",
        document_id="ec_test_law",
        chunk_index=0,
        content=(
            "La ley protege los datos personales."
        ),
        title="Ley de prueba",
        jurisdiction="ecuador",
        issuing_body="Asamblea Nacional",
        document_type="law",
        binding_level="binding",
        status="in_force",
        language="es",
        source_url="https://example.com/law",
        topics="protección de datos",
        checksum="a" * 64,
        distance=0.12,
    )


@pytest.mark.asyncio
async def test_search_legal_knowledge_tool(
    monkeypatch,
) -> None:
    """Comprueba entrada, agente y salida MCP."""

    def fake_agent(
        request: KnowledgeQuery,
    ) -> KnowledgeResponse:
        assert request.query == (
            "protección de datos personales"
        )
        assert request.top_k == 3
        assert request.jurisdiction == "ecuador"
        assert request.document_type == "law"

        return KnowledgeResponse(
            status="success",
            query=request.query,
            matches=[create_match()],
        )

    monkeypatch.setattr(
        knowledge_tools,
        "run_knowledge_agent",
        fake_agent,
    )

    result = await (
        knowledge_tools.search_legal_knowledge(
            query="protección de datos personales",
            top_k=3,
            jurisdiction="ecuador",
            document_type="law",
        )
    )

    assert result["status"] == "success"
    assert result["error"] is None
    assert len(result["matches"]) == 1
    assert (
        result["matches"][0]["document_id"]
        == "ec_test_law"
    )


@pytest.mark.asyncio
async def test_knowledge_tool_preserves_agent_error(
    monkeypatch,
) -> None:
    """Devuelve el error controlado del agente."""

    def fake_agent(
        request: KnowledgeQuery,
    ) -> KnowledgeResponse:
        return KnowledgeResponse(
            status="error",
            query=request.query,
            error="ChromaDB no disponible.",
        )

    monkeypatch.setattr(
        knowledge_tools,
        "run_knowledge_agent",
        fake_agent,
    )

    result = await (
        knowledge_tools.search_legal_knowledge(
            query="protección de datos"
        )
    )

    assert result["status"] == "error"
    assert result["matches"] == []
    assert result["error"] == (
        "ChromaDB no disponible."
    )