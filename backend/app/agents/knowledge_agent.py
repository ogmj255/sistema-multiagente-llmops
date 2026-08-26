import httpx
from chromadb.errors import ChromaError
from pydantic import ValidationError

from app.schemas.knowledge import (
    KnowledgeQuery,
    KnowledgeResponse,
)
from app.services.embeddings import (
    EmbeddingServiceError,
    generate_embeddings,
)
from app.services.legal_vector_store import (
    search_legal_chunks,
)


def run_knowledge_agent(
    request: KnowledgeQuery,
) -> KnowledgeResponse:
    """Recupera normativa relevante para una consulta."""

    try:
        query_embedding = generate_embeddings(
            [request.query]
        )[0]

        matches = search_legal_chunks(
            query_embedding,
            request,
        )
    except (
        ChromaError,
        EmbeddingServiceError,
        httpx.HTTPError,
        TypeError,
        ValidationError,
        ValueError,
    ) as error:
        return KnowledgeResponse(
            status="error",
            query=request.query,
            error=(
                "No se pudo consultar la base jurídica: "
                f"{error}"
            ),
        )

    return KnowledgeResponse(
        status="success",
        query=request.query,
        matches=matches,
    )