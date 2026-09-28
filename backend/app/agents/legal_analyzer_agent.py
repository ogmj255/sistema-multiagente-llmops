from dataclasses import dataclass

from app.agents.knowledge_agent import (
    run_knowledge_agent,
)
from app.schemas.knowledge import (
    KnowledgeQuery,
    LegalKnowledgeMatch,
)
from app.schemas.legal_analysis import (
    ClauseAnalysisRequest,
    ClauseAnalysisResponse,
)
from app.schemas.observability import LLMInvocationMetrics
from app.services.analysis import (
    ClauseClassificationError,
    LegalGroundingError,
    build_grounded_assessment,
    classify_clause,
)

LEGAL_CONTEXT_RESULTS = 5


@dataclass(frozen=True, slots=True)
class LegalAnalyzerExecution:
    """Resultado jurídico y telemetría real de una ejecución."""

    response: ClauseAnalysisResponse
    llm_metrics: LLMInvocationMetrics | None


def build_legal_search_query(
    request: ClauseAnalysisRequest,
) -> str:
    """Construye la consulta jurídica desde la cláusula."""

    parts: list[str] = []

    if request.clause.heading is not None:
        parts.append(
            f"Encabezado: {request.clause.heading}"
        )

    parts.append(
        f"Cláusula: {request.clause.content}"
    )

    return "\n".join(parts)


def run_legal_analyzer_execution_with_context(
    request: ClauseAnalysisRequest,
    legal_context: list[LegalKnowledgeMatch],
    trace_context: dict[str, str] | None = None,
) -> LegalAnalyzerExecution:
    """Analiza una cláusula conservando la telemetría del LLM."""

    try:
        if trace_context is None:
            execution = classify_clause(
                request,
                legal_context,
            )
        else:
            execution = classify_clause(
                request,
                legal_context,
                trace_context=trace_context,
            )
    except ClauseClassificationError as error:
        return LegalAnalyzerExecution(
            response=ClauseAnalysisResponse(
                status="error",
                error=(
                    f"No se pudo analizar la cláusula: {error}"
                ),
            ),
            llm_metrics=None,
        )

    model_response = execution.model_response

    total_tokens = (
        model_response.prompt_tokens
        + model_response.completion_tokens
        if model_response.prompt_tokens is not None
        and model_response.completion_tokens is not None
        else None
    )

    llm_metrics = LLMInvocationMetrics(
        provider=model_response.provider,
        model=model_response.model,
        prompt_tokens=model_response.prompt_tokens,
        completion_tokens=model_response.completion_tokens,
        total_tokens=total_tokens,
        cost_usd=model_response.cost_usd,
    )

    try:
        assessment = build_grounded_assessment(
            execution,
            request,
            legal_context,
        )
    except LegalGroundingError as error:
        return LegalAnalyzerExecution(
            response=ClauseAnalysisResponse(
                status="error",
                error=(
                    f"No se pudo analizar la cláusula: {error}"
                ),
            ),
            llm_metrics=llm_metrics,
        )

    return LegalAnalyzerExecution(
        response=ClauseAnalysisResponse(
            status="success",
            result=assessment,
        ),
        llm_metrics=llm_metrics,
    )


def run_legal_analyzer_with_context(
    request: ClauseAnalysisRequest,
    legal_context: list[LegalKnowledgeMatch],
    trace_context: dict[str, str] | None = None,
) -> ClauseAnalysisResponse:
    """Analiza una cláusula usando evidencia ya recuperada."""

    execution = run_legal_analyzer_execution_with_context(
        request,
        legal_context,
        trace_context,
    )

    return execution.response


def run_legal_analyzer_agent(
    request: ClauseAnalysisRequest,
) -> ClauseAnalysisResponse:
    """Recupera evidencia y analiza una cláusula."""

    legal_query = build_legal_search_query(request)

    knowledge_response = run_knowledge_agent(
        KnowledgeQuery(
            query=legal_query,
            top_k=LEGAL_CONTEXT_RESULTS,
        )
    )

    if knowledge_response.status == "error":
        legal_context: list[LegalKnowledgeMatch] = []
    else:
        legal_context = knowledge_response.matches

    return run_legal_analyzer_with_context(
        request,
        legal_context,
    )
