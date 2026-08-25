from pathlib import Path

from app.services.legal_corpus import (
    build_legal_corpus,
    load_legal_sources,
)

MINIMUM_DOCUMENTS = 50


def main() -> None:
    """Descarga y procesa el corpus jurídico definido."""

    sources = load_legal_sources(
        Path("data/legal_sources.json"),
        minimum_documents=MINIMUM_DOCUMENTS,
    )

    result = build_legal_corpus(
        sources=sources,
        raw_directory=Path("data/raw/legal"),
        processed_directory=Path("data/processed/legal"),
    )

    print("Solicitados:", result.requested)
    print("Completados:", result.completed)
    print("Fallidos:", result.failed)

    for error in result.errors:
        print(f"- {error.document_id}: {error.error}")

    if result.completed < MINIMUM_DOCUMENTS:
        raise SystemExit(
            "El corpus no alcanzó los 50 documentos requeridos."
        )


if __name__ == "__main__":
    main()