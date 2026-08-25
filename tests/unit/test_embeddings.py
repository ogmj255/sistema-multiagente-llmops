import httpx
import pytest
from app.services import embeddings


def test_generate_embeddings(monkeypatch) -> None:
    """Genera un vector por cada texto recibido."""

    monkeypatch.setattr(
        embeddings.settings,
        "ollama_embedding_dimensions",
        3,
    )

    def fake_post(
        url: str,
        *,
        json: dict[str, object],
        timeout: int,
    ) -> httpx.Response:
        assert url.endswith("/api/embed")
        assert json["model"] == "qwen3-embedding:0.6b"
        assert json["input"] == ["Protección de datos personales."]
        assert timeout == 60

        request = httpx.Request("POST", url)

        return httpx.Response(
            200,
            request=request,
            json={"embeddings": [[0.1, 0.2, 0.3]]},
        )

    monkeypatch.setattr(
        embeddings.httpx,
        "post",
        fake_post,
    )

    result = embeddings.generate_embeddings(["Protección de datos personales."])

    assert result == [[0.1, 0.2, 0.3]]


def test_reject_empty_embedding_input() -> None:
    """Rechaza listas vacías y textos sin contenido."""

    with pytest.raises(
        ValueError,
        match="al menos un texto no vacío",
    ):
        embeddings.generate_embeddings(["   "])


def test_reject_unexpected_dimensions(
    monkeypatch,
) -> None:
    """Controla vectores con dimensiones incorrectas."""

    monkeypatch.setattr(
        embeddings.settings,
        "ollama_embedding_dimensions",
        3,
    )

    def fake_post(
        url: str,
        *,
        json: dict[str, object],
        timeout: int,
    ) -> httpx.Response:
        request = httpx.Request("POST", url)

        return httpx.Response(
            200,
            request=request,
            json={"embeddings": [[0.1, 0.2]]},
        )

    monkeypatch.setattr(
        embeddings.httpx,
        "post",
        fake_post,
    )

    with pytest.raises(
        embeddings.EmbeddingServiceError,
        match="dimensiones esperadas",
    ):
        embeddings.generate_embeddings(["Contrato"])


def test_control_ollama_connection_error(
    monkeypatch,
) -> None:
    """Convierte los errores de conexión en errores del servicio."""

    def fail_post(
        url: str,
        *,
        json: dict[str, object],
        timeout: int,
    ) -> httpx.Response:
        raise httpx.ConnectError("Ollama no disponible.")

    monkeypatch.setattr(
        embeddings.httpx,
        "post",
        fail_post,
    )

    with pytest.raises(
        embeddings.EmbeddingServiceError,
        match="No se pudieron generar",
    ):
        embeddings.generate_embeddings(["Contrato"])
