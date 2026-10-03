from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.legal_analysis import ClauseAnalysisResponse


class LLMInvocationMetrics(BaseModel):
    """Métricas reales producidas por una invocación al LLM."""

    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    prompt_tokens: int | None = Field(
        default=None,
        ge=0,
    )
    completion_tokens: int | None = Field(
        default=None,
        ge=0,
    )
    total_tokens: int | None = Field(
        default=None,
        ge=0,
    )
    cost_usd: float | None = Field(
        default=None,
        ge=0,
    )


class ObservabilitySummary(BaseModel):
    """Resumen técnico consolidado de una ejecución."""

    status: Literal[
        "success",
        "partial",
        "error",
    ]
    provider: str | None = Field(
    default=None,
    min_length=1,
    )

    model: str | None = Field(
        default=None,
        min_length=1,
    )
    duration_ms: float = Field(ge=0)
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    cost_usd: float | None = Field(
        default=None,
        ge=0,
    )
    error_count: int = Field(ge=0)
    llm_invocation_count: int = Field(ge=0)

class LegalAnalyzerToolResponse(BaseModel):
    """Respuesta interna del MCP de análisis legal."""

    analysis: ClauseAnalysisResponse
    observability: LLMInvocationMetrics | None = None

class ObservabilityRunResponse(BaseModel):
    """Métricas persistidas de una ejecución para el dashboard."""

    execution_id: str = Field(min_length=1)
    
    execution_number: int = Field(ge=1)

    provider: str = Field(min_length=1)

    model: str = Field(min_length=1)

    platform: str | None = Field(
        default=None,
        min_length=1,
    )

    source_url: str | None = Field(
        default=None,
        min_length=1,
    )

    status: Literal[
        "success",
        "partial",
        "error",
    ]

    duration_ms: float = Field(ge=0)

    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)

    cost_usd: float | None = Field(
        default=None,
        ge=0,
    )

    error_count: int = Field(ge=0)

    llm_invocation_count: int = Field(ge=0)

    created_at: datetime

class LLMOpsDashboardResponse(BaseModel):
    """Datos agregados e históricos del dashboard LLMOps."""

    total_executions: int = Field(ge=0)
    average_latency_ms: float = Field(ge=0)
    total_tokens: int = Field(ge=0)
    total_cost_usd: float | None = Field(default=None, ge=0)
    error_rate_percent: float = Field(ge=0, le=100)
    total_errors: int = Field(ge=0)
    executions: list[ObservabilityRunResponse]
