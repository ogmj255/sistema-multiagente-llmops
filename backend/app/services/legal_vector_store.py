from collections.abc import Callable, Sequence

import chromadb
import httpx
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection
from chromadb.errors import ChromaError

from app.core.config import settings
from app.schemas.knowledge import (
    KnowledgeIndexResponse,
    KnowledgeQuery,
    LegalChunk,
    LegalKnowledgeMatch,
)
from app.services.embeddings import (
    EmbeddingServiceError,
    generate_embeddings,
)

INDEX_BATCH_SIZE = 32


def create_chroma_client() -> ClientAPI:
    """Crea el cliente HTTP de ChromaDB."""

    return chromadb.HttpClient(
        host=settings.chroma_host,
        port=settings.chroma_port,
    )


def get_legal_collection(
    client: ClientAPI | None = None,
) -> Collection:
    """Obtiene o crea la colección jurídica."""

    active_client = client or create_chroma_client()

    return active_client.get_or_create_collection(
        name=settings.chroma_collection,
        embedding_function=None,
        metadata={
            "description": (
                "Base de conocimiento jurídico"
            ),
            "embedding_model": (
                settings.ollama_embedding_model
            ),
            "embedding_dimensions": (
                settings.ollama_embedding_dimensions
            ),
        },
        configuration={
            "hnsw": {
                "space": "cosine",
            }
        },
    )


def build_chunk_metadata(
    chunk: LegalChunk,
) -> dict[str, str | int | float | bool]:
    """Convierte los metadatos al formato de ChromaDB."""

    payload = chunk.model_dump(
        mode="json",
        exclude={"content"},
    )
    metadata: dict[
        str,
        str | int | float | bool,
    ] = {}

    for key, value in payload.items():
        if isinstance(
            value,
            (str, int, float, bool),
        ):
            metadata[key] = value

    return metadata


def index_legal_chunks(
    chunks: Sequence[LegalChunk],
    preparation_errors: list[str] | None = None,
    batch_size: int = INDEX_BATCH_SIZE,
    collection: Collection | None = None,
        progress_callback: (
        Callable[[int, int], None] | None
    ) = None,
) -> KnowledgeIndexResponse:
    """Genera embeddings y carga segmentos por lotes."""

    if not chunks:
        return KnowledgeIndexResponse(
            status="error",
            documents=0,
            chunks=0,
            errors=["No existen segmentos para indexar."],
        )

    if batch_size < 1:
        raise ValueError(
            "El tamaño del lote debe ser positivo."
        )

    errors = list(preparation_errors or [])
    indexed_documents: set[str] = set()
    indexed_chunks = 0

    try:
        active_collection = (
            collection or get_legal_collection()
        )
    except (
        ChromaError,
        httpx.HTTPError,
        TypeError,
        ValueError,
    ) as error:
        return KnowledgeIndexResponse(
            status="error",
            documents=0,
            chunks=0,
            errors=[
                f"No se pudo acceder a ChromaDB: {error}"
            ],
        )

    for offset in range(
        0,
        len(chunks),
        batch_size,
    ):
        batch = list(
            chunks[offset : offset + batch_size]
        )

        batch_end = min(
            offset + len(batch),
            len(chunks),
        )
        try:
            vectors = generate_embeddings(
                [
                    chunk.content
                    for chunk in batch
                ]
            )

            active_collection.upsert(
                ids=[
                    chunk.chunk_id
                    for chunk in batch
                ],
                embeddings=vectors,
                documents=[
                    chunk.content
                    for chunk in batch
                ],
                metadatas=[
                    build_chunk_metadata(chunk)
                    for chunk in batch
                ],
            )
        except (
            ChromaError,
            EmbeddingServiceError,
            httpx.HTTPError,
            TypeError,
            ValueError,
        ) as error:
            batch_number = (
                offset // batch_size + 1
            )
            errors.append(
                f"Lote {batch_number}: {error}"
            )
            if progress_callback is not None:
                progress_callback(
                    batch_end,
                    len(chunks),
    )
            continue

        indexed_chunks += len(batch)
        indexed_documents.update(
            chunk.document_id
            for chunk in batch
        )
    if progress_callback is not None:
            progress_callback(
                batch_end,
                len(chunks),
        )
    if indexed_chunks == 0:
        status = "error"
    elif errors:
        status = "partial"
    else:
        status = "success"

    return KnowledgeIndexResponse(
        status=status,
        documents=len(indexed_documents),
        chunks=indexed_chunks,
        errors=errors,
    )
def build_query_filter(
    request: KnowledgeQuery,
) -> dict[str, object] | None:
    """Construye filtros opcionales para ChromaDB."""

    filters: list[dict[str, object]] = []

    if request.jurisdiction is not None:
        filters.append(
            {
                "jurisdiction": (
                    request.jurisdiction
                )
            }
        )

    if request.document_type is not None:
        filters.append(
            {
                "document_type": (
                    request.document_type
                )
            }
        )

    if not filters:
        return None

    if len(filters) == 1:
        return filters[0]

    return {"$and": filters}


def search_legal_chunks(
    query_embedding: list[float],
    request: KnowledgeQuery,
    collection: Collection | None = None,
) -> list[LegalKnowledgeMatch]:
    """Recupera los segmentos jurídicos más cercanos."""

    if (
        len(query_embedding)
        != settings.ollama_embedding_dimensions
    ):
        raise ValueError(
            "El embedding de consulta tiene "
            "dimensiones incorrectas."
        )

    active_collection = (
        collection or get_legal_collection()
    )

    collection_size = active_collection.count()

    if collection_size == 0:
        raise ValueError(
            "La base jurídica no contiene segmentos."
        )

    candidate_count = min(
        collection_size,
        request.top_k * 2,
    )

    result = active_collection.query(
        query_embeddings=[query_embedding],
        n_results=candidate_count,
        where=build_query_filter(request),
        include=[
            "documents",
            "metadatas",
            "distances",
        ],
    )

    ids = result.get("ids")
    documents = result.get("documents")
    metadatas = result.get("metadatas")
    distances = result.get("distances")

    if (
        ids is None
        or documents is None
        or metadatas is None
        or distances is None
        or not ids
    ):
        raise ValueError(
            "ChromaDB devolvió una respuesta incompleta."
        )

    matches: list[LegalKnowledgeMatch] = []
    seen_contents: set[tuple[str, str]] = set()

    for (
        chunk_id,
        content,
        metadata,
        distance,
    ) in zip(
        ids[0],
        documents[0],
        metadatas[0],
        distances[0],
        strict=True,
    ):
        if (
            content is None
            or metadata is None
            or distance is None
        ):
            raise ValueError(
                "ChromaDB devolvió un resultado inválido."
            )

        payload = dict(metadata)
        payload.update(
            {
                "chunk_id": chunk_id,
                "content": content,
                "distance": distance,
            }
        )

        match = LegalKnowledgeMatch.model_validate(
            payload
        )
        content_key = (
            match.document_id,
            match.content,
        )

        if content_key in seen_contents:
            continue

        seen_contents.add(content_key)
        matches.append(match)

        if len(matches) == request.top_k:
            break

    return matches