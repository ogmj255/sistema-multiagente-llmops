import pytest
from app.mcp import report_generator_tools
from app.schemas.report import (
    AnalysisReport,
    ReportGenerationRequest,
    ReportGenerationResponse,
    RiskSummary,
)


@pytest.mark.asyncio
async def test_generate_analysis_report_invoca_agente(
    monkeypatch,
) -> None:
    request = ReportGenerationRequest(
        execution_id="ejecucion-1",
        source_url="https://example.com/terms",
        platform="Example",
        title="Terms of Service",
        language="es",
        total_clauses=0,
        clauses=[],
    )

    expected = ReportGenerationResponse(
        status="success",
        report=AnalysisReport(
            execution_id=request.execution_id,
            source_url=request.source_url,
            platform=request.platform,
            title=request.title,
            language=request.language,
            total_clauses=0,
            analyzed_clauses=0,
            successful_clauses=0,
            failed_clauses=0,
            risk_summary=RiskSummary(),
            clauses=[],
        ),
    )

    def fake_agent(
        received_request: ReportGenerationRequest,
    ) -> ReportGenerationResponse:
        assert received_request == request
        return expected

    monkeypatch.setattr(
        report_generator_tools,
        "run_report_generator_agent",
        fake_agent,
    )

    result = await report_generator_tools.generate_analysis_report(
        request
    )

    assert result == expected.model_dump(mode="json")
