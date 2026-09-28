from mcp.server.fastmcp import FastMCP

from app.agents.observability_agent import (
    build_observability_summary,
)
from app.schemas.observability import (
    LLMInvocationMetrics,
)
from app.schemas.orchestration import PipelineStatus

mcp = FastMCP("Agente de Observabilidad")


@mcp.tool()
def build_execution_observability(
    status: PipelineStatus,
    duration_ms: float,
    llm_metrics: list[LLMInvocationMetrics],
    error_count: int,
) -> dict[str, object]:
    """Consolida las métricas reales de una ejecución."""

    summary = build_observability_summary(
        status=status,
        duration_ms=duration_ms,
        llm_metrics=llm_metrics,
        error_count=error_count,
    )

    return summary.model_dump(mode="json")


if __name__ == "__main__":
    mcp.run()
