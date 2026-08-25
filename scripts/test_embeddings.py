from app.core.config import settings
from app.services.embeddings import generate_embeddings


def main() -> None:
    """Verifica la generación real de embeddings con Ollama."""

    texts = [
        "El proveedor protegerá los datos personales.",
        "The provider shall protect personal data.",
    ]

    vectors = generate_embeddings(texts)

    dimensions = {len(vector) for vector in vectors}

    if dimensions != {settings.ollama_embedding_dimensions}:
        raise RuntimeError("Los vectores tienen dimensiones inconsistentes.")

    print("Servidor:", settings.ollama_base_url)
    print("Modelo:", settings.ollama_embedding_model)
    print("Textos procesados:", len(texts))
    print("Vectores generados:", len(vectors))
    print(
        "Dimensiones:",
        settings.ollama_embedding_dimensions,
    )
    print("Estado: success")


if __name__ == "__main__":
    main()
