from mcp.server.fastmcp import FastMCP

from app.agents.preprocessor_agent import (
    run_preprocessor_agent,
)
from app.schemas.contract import ExtractedContract

mcp = FastMCP("Agente Preprocesador")


@mcp.tool()
def preprocess_saas_terms(
    contract: ExtractedContract,
) -> dict[str, object]:
    """Limpia y segmenta un contrato extraído."""

    response = run_preprocessor_agent(contract)
    return response.model_dump(mode="json")


if __name__ == "__main__":
    mcp.run()