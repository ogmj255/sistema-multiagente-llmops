from datetime import UTC, datetime

from app.mcp import preprocessor_tools
from app.schemas.contract import ExtractedContract
from app.schemas.preprocessing import PreprocessingResponse


def test_preprocess_saas_terms_tool(monkeypatch) -> None:
    """Comprueba que la herramienta MCP llama al preprocesador."""

    contract = ExtractedContract(
        source_url="https://example.com/terms",
        platform="Example",
        retrieved_at=datetime.now(UTC),
        extraction_method="httpx",
        raw_html="""
        <html lang="en">
            <body>
                <main>
                    <p>Contractual condition.</p>
                </main>
            </body>
        </html>
        """,
    )

    def fake_agent(
        received_contract: ExtractedContract,
    ) -> PreprocessingResponse:
        assert received_contract == contract

        return PreprocessingResponse(
            status="error",
            error="Prueba controlada.",
        )

    monkeypatch.setattr(
        preprocessor_tools,
        "run_preprocessor_agent",
        fake_agent,
    )

    result = preprocessor_tools.preprocess_saas_terms(
        contract
    )

    assert result["status"] == "error"
    assert result["error"] == "Prueba controlada."
