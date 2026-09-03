from asyncio import to_thread

from mcp.server.fastmcp import FastMCP

from app.agents.legal_analyzer_agent import (
    run_legal_analyzer_agent,
)
from app.schemas.legal_analysis import (
    ClauseAnalysisRequest,
)
from app.schemas.legal_corpus import Jurisdiction
from app.schemas.preprocessing import ProcessedClause

mcp = FastMCP("Agente Analizador Legal")


@mcp.tool()
async def analyze_legal_clause(
    source_url: str,
    platform: str,
    language: str,
    clause: ProcessedClause,
    jurisdiction: Jurisdiction = "ecuador",
) -> dict[str, object]:
    """Analiza jurídicamente una cláusula SaaS."""

    request = ClauseAnalysisRequest(
        source_url=source_url,
        platform=platform,
        language=language,
        jurisdiction=jurisdiction,
        clause=clause,
    )

    response = await to_thread(
        run_legal_analyzer_agent,
        request,
    )

    return response.model_dump(mode="json")


if __name__ == "__main__":
    mcp.run()