import httpx

from app.core.config import settings

EMBEDDING_BATCH_SIZE = 64


class EmbeddingServiceError(RuntimeError):
    """Indica que Ollama no pudo generar embeddings v?lidos."""


def generate_embeddings(
    texts: list[str],
) -> list[list[float]]:
    """Genera embeddings mediante la API local de Ollama."""

    if not texts or any(
        not text.strip()
        for text in texts
    ):
        raise ValueError(
            "Se requiere al menos un texto no vacío."
        )

    embeddings: list[list[float]] = []

    try:
        for start in range(
            0,
            len(texts),
            EMBEDDING_BATCH_SIZE,
        ):
            batch = texts[
                start : start + EMBEDDING_BATCH_SIZE
            ]

            response = httpx.post(
                (
                    f"{settings.ollama_base_url.rstrip('/')}"
                    "/api/embed"
                ),
                json={
                    "model": (
                        settings.ollama_embedding_model
                    ),
                    "input": batch,
                },
                timeout=60,
            )
            response.raise_for_status()

            batch_embeddings = response.json()[
                "embeddings"
            ]

            if (
                not isinstance(
                    batch_embeddings,
                    list,
                )
                or len(batch_embeddings)
                != len(batch)
            ):
                raise EmbeddingServiceError(
                    "Ollama devolvi? una cantidad "
                    "inesperada de vectores."
                )

            embeddings.extend(
                batch_embeddings
            )

    except EmbeddingServiceError:
        raise
    except (
        httpx.HTTPError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        raise EmbeddingServiceError(
            "No se pudieron generar los "
            f"embeddings: {exc}"
        ) from exc

    if len(embeddings) != len(texts):
        raise EmbeddingServiceError(
            "Ollama devolvi? una cantidad "
            "inesperada de vectores."
        )

    vectors: list[list[float]] = []

    for embedding in embeddings:
        if (
            not isinstance(embedding, list)
            or len(embedding)
            != settings.ollama_embedding_dimensions
            or any(
                not isinstance(value, (int, float))
                for value in embedding
            )
        ):
            raise EmbeddingServiceError(
                "El vector no tiene las "
                "dimensiones esperadas."
            )

        vectors.append(
            [
                float(value)
                for value in embedding
            ]
        )

    return vectors
