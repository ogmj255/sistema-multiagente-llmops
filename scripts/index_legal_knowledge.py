from pathlib import Path
from time import perf_counter

from app.core.config import settings
from app.services.legal_knowledge import (
    prepare_legal_chunks,
)
from app.services.legal_vector_store import (
    INDEX_BATCH_SIZE,
    get_legal_collection,
    index_legal_chunks,
)

PROCESSED_DIRECTORY = Path(
    "data/processed/legal"
)
CHUNKS_PATH = Path(
    "data/processed/legal_chunks.jsonl"
)


def show_progress(
    processed: int,
    total: int,
) -> None:
    """Muestra avances periódicos de la indexación."""

    interval = INDEX_BATCH_SIZE * 10

    if processed == total or processed % interval == 0:
        print(
            f"Progreso: {processed}/{total}"
        )


def main() -> None:
    """Prepara e indexa el corpus jurídico completo."""

    started_at = perf_counter()

    chunks, preparation_errors = (
        prepare_legal_chunks(
            processed_directory=(
                PROCESSED_DIRECTORY
            ),
            output_path=CHUNKS_PATH,
        )
    )

    print("Segmentos preparados:", len(chunks))
    print(
        "Errores de preparación:",
        len(preparation_errors),
    )

    result = index_legal_chunks(
        chunks,
        preparation_errors=preparation_errors,
        progress_callback=show_progress,
    )

    collection = get_legal_collection()
    elapsed = perf_counter() - started_at

    print("Estado:", result.status)
    print("Documentos indexados:", result.documents)
    print("Segmentos indexados:", result.chunks)
    print(
        "Registros en ChromaDB:",
        collection.count(),
    )
    print(
        "Colección:",
        settings.chroma_collection,
    )
    print(f"Tiempo: {elapsed:.2f} segundos")
    print("Errores:", len(result.errors))

    for error in result.errors:
        print("-", error)

    if result.status == "error":
        raise SystemExit(1)


if __name__ == "__main__":
    main()