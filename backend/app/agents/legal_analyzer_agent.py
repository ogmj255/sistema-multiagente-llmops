from app.agents.knowledge_agent import (
    run_knowledge_agent,
)
from app.schemas.knowledge import KnowledgeQuery
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
        parts.append(
            f"Encabezado: {request.clause.heading}."
        )

    parts.append(
        f"Cláusula: {request.clause.content}"
    )

    return "\n".join(parts)


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
            error=(
                "No se pudo analizar la cláusula: "
                f"{detail}"
            ),
        )

    if not knowledge_response.matches:
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
            knowledge_response.matches,
        )
        assessment = build_grounded_assessment(
            execution,
            knowledge_response.matches,
        )
    except (
        ClauseClassificationError,
        LegalGroundingError,
    ) as error:
        return ClauseAnalysisResponse(
            status="error",
            error=(
                "No se pudo analizar la cláusula: "
                f"{error}"
            ),
        )

    return ClauseAnalysisResponse(
        status="success",
        result=assessment,
    )