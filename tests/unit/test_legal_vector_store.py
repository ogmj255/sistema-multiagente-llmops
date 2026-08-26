import pytest
from app.schemas.knowledge import (
    KnowledgeQuery,
    LegalChunk,
)
from app.services import legal_vector_store
from app.services.embeddings import (
    EmbeddingServiceError,
)


class FakeCollection:
    """Simula las operaciones necesarias de ChromaDB."""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def upsert(
        self,
        *,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[
            dict[str, str | int | float | bool]
        ],
    ) -> None:
        self.calls.append(
            {
                "ids": ids,
                "embeddings": embeddings,
                "documents": documents,
                "metadatas": metadatas,
            }
        )


def create_chunk(index: int) -> LegalChunk:
    """Crea un segmento jurídico para pruebas."""

    return LegalChunk(
        chunk_id=(
            f"ec_test_law_chunk_{index:04d}"
        ),
        document_id="ec_test_law",
        chunk_index=index,
        content=f"Contenido jurídico {index}.",
        title="Ley de prueba",
        jurisdiction="ecuador",
        issuing_body="Asamblea Nacional",
        document_type="law",
        binding_level="binding",
        status="in_force",
        language="es",
        source_url="https://example.com/law",
        topics="protección de datos",
        checksum="a" * 64,
    )


def test_build_chunk_metadata() -> None:
    """Convierte metadatos y excluye contenido y nulos."""

    metadata = (
        legal_vector_store.build_chunk_metadata(
            create_chunk(0)
        )
    )

    assert metadata["chunk_id"] == (
        "ec_test_law_chunk_0000"
    )
    assert metadata["chunk_index"] == 0
    assert metadata["jurisdiction"] == "ecuador"
    assert "content" not in metadata
    assert "official_citation" not in metadata


def test_index_legal_chunks_in_batches(
    monkeypatch,
) -> None:
    """Indexa todos los segmentos en lotes reproducibles."""

    collection = FakeCollection()
    chunks = [
        create_chunk(index)
        for index in range(3)
    ]

    def fake_embeddings(
        texts: list[str],
    ) -> list[list[float]]:
        return [
            [float(index), 0.0, 1.0]
            for index, _ in enumerate(texts)
        ]

    monkeypatch.setattr(
        legal_vector_store,
        "generate_embeddings",
        fake_embeddings,
    )

    result = (
        legal_vector_store.index_legal_chunks(
            chunks,
            batch_size=2,
            collection=collection,
        )
    )

    assert result.status == "success"
    assert result.documents == 1
    assert result.chunks == 3
    assert result.errors == []
    assert len(collection.calls) == 2
    assert collection.calls[0]["ids"] == [
        "ec_test_law_chunk_0000",
        "ec_test_law_chunk_0001",
    ]


def test_index_continues_after_batch_error(
    monkeypatch,
) -> None:
    """Continúa con el siguiente lote cuando uno falla."""

    collection = FakeCollection()
    calls = 0

    def fail_first_batch(
        texts: list[str],
    ) -> list[list[float]]:
        nonlocal calls
        calls += 1

        if calls == 1:
            raise EmbeddingServiceError(
                "Fallo controlado."
            )

        return [[0.0, 1.0, 0.0]]

    monkeypatch.setattr(
        legal_vector_store,
        "generate_embeddings",
        fail_first_batch,
    )

    result = (
        legal_vector_store.index_legal_chunks(
            [
                create_chunk(0),
                create_chunk(1),
                create_chunk(2),
            ],
            batch_size=2,
            collection=collection,
        )
    )

    assert result.status == "partial"
    assert result.chunks == 1
    assert len(result.errors) == 1
    assert result.errors[0].startswith("Lote 1:")
    assert len(collection.calls) == 1


def test_reject_empty_index() -> None:
    """Devuelve error controlado sin segmentos."""

    result = (
        legal_vector_store.index_legal_chunks([])
    )

    assert result.status == "error"
    assert result.documents == 0
    assert result.chunks == 0
    assert result.errors
class FakeSearchCollection:
    """Simula una colección con resultados jurídicos."""

    def __init__(self) -> None:
        self.where: dict[str, object] | None = None

    def count(self) -> int:
        return 1

    def query(
        self,
        *,
        query_embeddings: list[list[float]],
        n_results: int,
        where: dict[str, object] | None,
        include: list[str],
    ) -> dict[str, object]:
        self.where = where

        assert query_embeddings == [
            [0.1, 0.2, 0.3]
        ]
        assert n_results == 3
        assert include == [
            "documents",
            "metadatas",
            "distances",
        ]

        return {
            "ids": [[
                "ec_test_law_chunk_0000"
            ]],
            "documents": [[
                "La ley protege los datos personales."
            ]],
            "metadatas": [[{
                "document_id": "ec_test_law",
                "chunk_index": 0,
                "title": "Ley de prueba",
                "jurisdiction": "ecuador",
                "issuing_body": (
                    "Asamblea Nacional"
                ),
                "document_type": "law",
                "binding_level": "binding",
                "status": "in_force",
                "language": "es",
                "source_url": (
                    "https://example.com/law"
                ),
                "topics": "protección de datos",
                "checksum": "a" * 64,
            }]],
            "distances": [[0.12]],
        }


def test_search_legal_chunks_with_filters(
    monkeypatch,
) -> None:
    """Recupera y valida resultados con filtros."""

    monkeypatch.setattr(
        legal_vector_store.settings,
        "ollama_embedding_dimensions",
        3,
    )

    collection = FakeSearchCollection()
    request = KnowledgeQuery(
        query="protección de datos",
        top_k=3,
        jurisdiction="ecuador",
        document_type="law",
    )

    matches = (
        legal_vector_store.search_legal_chunks(
            [0.1, 0.2, 0.3],
            request,
            collection=collection,
        )
    )

    assert len(matches) == 1
    assert matches[0].document_id == (
        "ec_test_law"
    )
    assert matches[0].distance == 0.12
    assert collection.where == {
        "$and": [
            {"jurisdiction": "ecuador"},
            {"document_type": "law"},
        ]
    }


def test_search_rejects_empty_collection(
    monkeypatch,
) -> None:
    """Controla una colección jurídica vacía."""

    monkeypatch.setattr(
        legal_vector_store.settings,
        "ollama_embedding_dimensions",
        3,
    )

    collection = FakeSearchCollection()
    collection.count = lambda: 0

    with pytest.raises(
        ValueError,
        match="no contiene segmentos",
    ):
        legal_vector_store.search_legal_chunks(
            [0.1, 0.2, 0.3],
            KnowledgeQuery(
                query="protección de datos"
            ),
            collection=collection,
        )