from asyncio import to_thread

from mcp.server.fastmcp import FastMCP

from app.agents.legal_analyzer_agent import (
    run_legal_analyzer_execution_with_context,
)
from app.schemas.knowledge import LegalKnowledgeMatch
from app.schemas.legal_analysis import ClauseAnalysisRequest
from app.schemas.observability import LegalAnalyzerToolResponse
from app.schemas.preprocessing import ProcessedClause

mcp = FastMCP("Agente Analizador Legal")


@mcp.tool()
async def analyze_legal_clause(
    source_url: str,
    platform: str,
    language: str,
    clause: ProcessedClause,
    legal_context: list[LegalKnowledgeMatch],
    trace_context: dict[str, str] | None = None,
) -> dict[str, object]:
    """Analiza una cláusula y devuelve resultado y telemetría."""

    request = ClauseAnalysisRequest(
        source_url=source_url,
        platform=platform,
        language=language,
        clause=clause,
    )

    if trace_context is None:
        execution = await to_thread(
            run_legal_analyzer_execution_with_context,
            request,
            legal_context,
        )
    else:
        execution = await to_thread(
            run_legal_analyzer_execution_with_context,
            request,
            legal_context,
            trace_context,
        )

    response = LegalAnalyzerToolResponse(
        analysis=execution.response,
        observability=execution.llm_metrics,
    )

    return response.model_dump(mode="json")


if __name__ == "__main__":
    mcp.run()
