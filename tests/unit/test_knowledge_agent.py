from app.agents import knowledge_agent
from app.schemas.knowledge import (
    KnowledgeQuery,
    LegalKnowledgeMatch,
)
from app.services.embeddings import (
    EmbeddingServiceError,
)


def create_match() -> LegalKnowledgeMatch:
    """Crea un resultado jurídico válido."""

    return LegalKnowledgeMatch(
        chunk_id="ec_test_law_chunk_0000",
        document_id="ec_test_law",
        chunk_index=0,
        content=(
            "La ley protege los datos personales."
        ),
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
        distance=0.12,
    )


def test_knowledge_agent_returns_matches(
    monkeypatch,
) -> None:
    """Genera el embedding y recupera normativa."""

    request = KnowledgeQuery(
        query="¿Cómo se protegen los datos?",
        top_k=3,
    )

    def fake_embeddings(
        texts: list[str],
    ) -> list[list[float]]:
        assert texts == [request.query]
        return [[0.1, 0.2, 0.3]]

    def fake_search(
        query_embedding: list[float],
        received_request: KnowledgeQuery,
    ) -> list[LegalKnowledgeMatch]:
        assert query_embedding == [
            0.1,
            0.2,
            0.3,
        ]
        assert received_request == request
        return [create_match()]

    monkeypatch.setattr(
        knowledge_agent,
        "generate_embeddings",
        fake_embeddings,
    )
    monkeypatch.setattr(
        knowledge_agent,
        "search_legal_chunks",
        fake_search,
    )

    response = (
        knowledge_agent.run_knowledge_agent(
            request
        )
    )

    assert response.status == "success"
    assert response.error is None
    assert len(response.matches) == 1
    assert response.matches[0].document_id == (
        "ec_test_law"
    )


def test_knowledge_agent_controls_error(
    monkeypatch,
) -> None:
    """Devuelve error sin interrumpir el flujo."""

    def fail_embeddings(
        texts: list[str],
    ) -> list[list[float]]:
        raise EmbeddingServiceError(
            "Ollama no disponible."
        )

    monkeypatch.setattr(
        knowledge_agent,
        "generate_embeddings",
        fail_embeddings,
    )

    response = (
        knowledge_agent.run_knowledge_agent(
            KnowledgeQuery(
                query="protección de datos"
            )
        )
    )

    assert response.status == "error"
    assert response.matches == []
    assert response.error is not None
    assert "base jurídica" in response.error