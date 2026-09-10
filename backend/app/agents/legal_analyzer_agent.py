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
from app.services.analysis import (
    ClauseClassificationError,
    LegalGroundingError,
    build_grounded_assessment,
    classify_clause,
)

LEGAL_CONTEXT_RESULTS = 5


def build_legal_search_query(
    request: ClauseAnalysisRequest,
) -> str:
    """Construye la consulta jurídica desde la cláusula."""

    parts = [
        (
            "Normativa aplicable para evaluar una "
            "cláusula de términos de servicio SaaS, "
            "considerando obligaciones del proveedor, "
            "derechos del usuario y posibles "
            "restricciones contractuales."
        ),
        f"Jurisdicción: {request.jurisdiction}.",
    ]

    if request.clause.heading is not None:
        parts.append(f"Encabezado: {request.clause.heading}.")

    parts.append(f"Cláusula: {request.clause.content}")

    return "\n".join(parts)


def run_legal_analyzer_with_context(
    request: ClauseAnalysisRequest,
    legal_context: list[LegalKnowledgeMatch],
) -> ClauseAnalysisResponse:
    """Analiza una cláusula usando evidencia ya recuperada."""

    if not legal_context:
        return ClauseAnalysisResponse(
            status="error",
            error=(
                "No se pudo analizar la cláusula: "
                "el RAG no recuperó evidencia jurídica."
            ),
        )

    try:
        execution = classify_clause(
            request,
            legal_context,
        )
        assessment = build_grounded_assessment(
            execution,
            request,
            legal_context,
        )
    except (
        ClauseClassificationError,
        LegalGroundingError,
    ) as error:
        return ClauseAnalysisResponse(
            status="error",
            error=(f"No se pudo analizar la cláusula: {error}"),
        )

    return ClauseAnalysisResponse(
        status="success",
        result=assessment,
    )


def run_legal_analyzer_agent(
    request: ClauseAnalysisRequest,
) -> ClauseAnalysisResponse:
    """Recupera evidencia y analiza una cláusula."""

    legal_query = build_legal_search_query(request)

    knowledge_response = run_knowledge_agent(
        KnowledgeQuery(
            query=legal_query,
            top_k=LEGAL_CONTEXT_RESULTS,
            jurisdiction=request.jurisdiction,
        )
    )

    if knowledge_response.status == "error":
        detail = (
            knowledge_response.error
            or "Error desconocido en el RAG jurídico."
        )

        return ClauseAnalysisResponse(
            status="error",
            error=(f"No se pudo analizar la cláusula: {detail}"),
        )
    return run_legal_analyzer_with_context(
        request,
        knowledge_response.matches,
    )
