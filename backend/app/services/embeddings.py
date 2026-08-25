import httpx

from app.core.config import settings


class EmbeddingServiceError(RuntimeError):
    """Indica que Ollama no pudo generar embeddings válidos."""


def generate_embeddings(
    texts: list[str],
) -> list[list[float]]:
    """Genera embeddings mediante la API local de Ollama."""

    if not texts or any(not text.strip() for text in texts):
        raise ValueError("Se requiere al menos un texto no vacío.")

    try:
        response = httpx.post(
            (f"{settings.ollama_base_url.rstrip('/')}/api/embed"),
            json={
                "model": settings.ollama_embedding_model,
                "input": texts,
            },
            timeout=60,
        )
        response.raise_for_status()
        embeddings = response.json()["embeddings"]
    except (
        httpx.HTTPError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        raise EmbeddingServiceError(
            f"No se pudieron generar los embeddings: {exc}"
        ) from exc

    if not isinstance(embeddings, list) or len(embeddings) != len(texts):
        raise EmbeddingServiceError(
            "Ollama devolvió una cantidad inesperada de vectores."
        )

    vectors: list[list[float]] = []

    for embedding in embeddings:
        if (
            not isinstance(embedding, list)
            or len(embedding) != settings.ollama_embedding_dimensions
            or any(not isinstance(value, (int, float)) for value in embedding)
        ):
            raise EmbeddingServiceError("El vector no tiene las dimensiones esperadas.")

        vectors.append([float(value) for value in embedding])

    return vectors
