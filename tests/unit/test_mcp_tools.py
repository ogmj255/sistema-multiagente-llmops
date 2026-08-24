import pytest
from app.mcp import tools
from app.schemas.contract import ExtractionRequest, ExtractionResponse


@pytest.mark.asyncio
async def test_extract_saas_terms_tool(monkeypatch) -> None:
    """Comprueba que la herramienta MCP llama al agente Web Scraper."""

    def fake_agent(
        request: ExtractionRequest,
    ) -> ExtractionResponse:
        assert str(request.url) == "https://example.com/terms"
        assert request.platform == "Example"

        return ExtractionResponse(
            status="error",
            error="Prueba controlada.",
        )

    monkeypatch.setattr(
        tools,
        "run_web_scraper_agent",
        fake_agent,
    )

    result = await tools.extract_saas_terms(
        url="https://example.com/terms",
        platform="Example",
    )

    assert result["status"] == "error"
    assert result["error"] == "Prueba controlada."
