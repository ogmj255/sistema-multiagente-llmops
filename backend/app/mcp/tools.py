from mcp.server.fastmcp import FastMCP

from app.agents.web_scraper_agent import run_web_scraper_agent
from app.schemas.contract import ExtractionRequest

mcp = FastMCP("Agente Web Scraper")


@mcp.tool()
def extract_saas_terms(
    url: str,
    platform: str | None = None,
) -> dict[str, object]:
    """Extrae los términos de servicio publicados en una página web."""

    request = ExtractionRequest(
        url=url,
        platform=platform,
    )

    response = run_web_scraper_agent(request)

    return response.model_dump(mode="json")


if __name__ == "__main__":
    mcp.run()
