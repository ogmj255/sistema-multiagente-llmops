from asyncio import to_thread

from mcp.server.fastmcp import FastMCP

from app.agents.legal_analyzer_agent import (
    run_legal_analyzer_with_context,
)
from app.schemas.knowledge import LegalKnowledgeMatch
from app.schemas.legal_analysis import (
    ClauseAnalysisRequest,
)
from app.schemas.preprocessing import ProcessedClause

mcp = FastMCP("Agente Analizador Legal")


@mcp.tool()
async def analyze_legal_clause(
    source_url: str,
    platform: str,
    language: str,
    clause: ProcessedClause,
    legal_context: list[LegalKnowledgeMatch],
) -> dict[str, object]:
    """Analiza una cláusula usando evidencia jurídica recuperada."""

    request = ClauseAnalysisRequest(
        source_url=source_url,
        platform=platform,
        language=language,
        clause=clause,
    )

    response = await to_thread(
        run_legal_analyzer_with_context,
        request,
        legal_context,
    )

    return response.model_dump(mode="json")


if __name__ == "__main__":
    mcp.run()
