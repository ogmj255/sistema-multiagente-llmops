from mcp.server.fastmcp import FastMCP

from app.agents.report_generator_agent import (
    run_report_generator_agent,
)
from app.schemas.report import ReportGenerationRequest

mcp = FastMCP("Agente Generador de Informes")


@mcp.tool()
async def generate_analysis_report(
    request: ReportGenerationRequest,
) -> dict[str, object]:
    """Genera el informe estructurado del análisis contractual."""

    response = run_report_generator_agent(request)

    return response.model_dump(mode="json")


if __name__ == "__main__":
    mcp.run()
