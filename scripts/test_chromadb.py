import chromadb
from app.core.config import settings

COLLECTION_NAME = "configuration_test"
TEST_ID = "configuration_vector"


def main() -> None:
    """Comprueba las operaciones básicas de ChromaDB."""

    client = chromadb.HttpClient(
        host=settings.chroma_host,
        port=settings.chroma_port,
    )

    heartbeat = client.heartbeat()

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
    )

    collection.upsert(
        ids=[TEST_ID],
        embeddings=[[1.0, 0.0, 0.0]],
        documents=["Prueba funcional de ChromaDB."],
        metadatas=[{"type": "configuration_test"}],
    )

    result = collection.query(
        query_embeddings=[[1.0, 0.0, 0.0]],
        n_results=1,
    )

    if result["ids"][0][0] != TEST_ID:
        raise RuntimeError(
            "ChromaDB no recuperó el vector esperado."
        )

    print(
        "Servidor:",
        f"{settings.chroma_host}:{settings.chroma_port}",
    )
    print("Heartbeat:", heartbeat)
    print("Resultado:", result["ids"][0][0])
    print("Estado: success")

    client.delete_collection(
        name=COLLECTION_NAME,
    )


if __name__ == "__main__":
    main()