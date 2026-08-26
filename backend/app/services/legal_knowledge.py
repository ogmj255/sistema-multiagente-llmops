import json
from pathlib import Path

from pydantic import ValidationError

from app.schemas.knowledge import LegalChunk
from app.schemas.legal_corpus import LegalDocument

MAX_CHUNK_LENGTH = 1200
CHUNK_OVERLAP = 200


def split_legal_text(
    text: str,
    max_length: int = MAX_CHUNK_LENGTH,
    overlap: int = CHUNK_OVERLAP,
) -> list[str]:
    """Divide texto jurídico priorizando límites naturales."""

    if max_length < 1:
        raise ValueError(
            "La longitud máxima debe ser positiva."
        )

    if overlap < 0 or overlap >= max_length:
        raise ValueError(
            "El solapamiento debe ser menor que la longitud."
        )

    normalized = "\n".join(
        line.strip()
        for line in text.splitlines()
        if line.strip()
    )

    if not normalized:
        raise ValueError(
            "El documento no contiene texto utilizable."
        )

    chunks: list[str] = []
    start = 0

    while start < len(normalized):
        maximum_end = min(
            start + max_length,
            len(normalized),
        )
        end = maximum_end

        if maximum_end < len(normalized):
            boundary = normalized.rfind(
                "\n",
                start + 1,
                maximum_end,
            )

            if boundary <= start + max_length // 2:
                boundary = normalized.rfind(
                    " ",
                    start + 1,
                    maximum_end,
                )

            if boundary > start:
                end = boundary

        chunk = normalized[start:end].strip()

        if chunk and (
            not chunks or chunk != chunks[-1]
        ):
            chunks.append(chunk)

        if end >= len(normalized):
            break

        next_start = max(
            end - overlap,
            start + 1,
        )

        while (
            next_start < end
            and next_start > 0
            and not normalized[next_start - 1].isspace()
        ):
            next_start += 1

        start = next_start

    return chunks


def prepare_legal_document(
    document: LegalDocument,
) -> list[LegalChunk]:
    """Prepara los segmentos de un documento jurídico."""

    source = document.source
    contents = split_legal_text(document.content)

    return [
        LegalChunk(
            chunk_id=(
                f"{source.document_id}_chunk_"
                f"{index:04d}"
            ),
            document_id=source.document_id,
            chunk_index=index,
            content=content,
            title=source.title,
            jurisdiction=source.jurisdiction,
            issuing_body=source.issuing_body,
            document_type=source.document_type,
            binding_level=source.binding_level,
            status=source.status,
            language=source.language,
            source_url=source.source_url,
            official_citation=source.official_citation,
            publication_date=source.publication_date,
            effective_date=source.effective_date,
            topics="|".join(source.topics),
            checksum=document.checksum,
        )
        for index, content in enumerate(contents)
    ]


def prepare_legal_chunks(
    processed_directory: Path,
    output_path: Path,
    minimum_documents: int = 50,
) -> tuple[list[LegalChunk], list[str]]:
    """Prepara el corpus sin detenerse por errores individuales."""

    paths = sorted(
        processed_directory.glob("*.json")
    )

    if len(paths) < minimum_documents:
        raise ValueError(
            "No existen al menos "
            f"{minimum_documents} documentos procesados."
        )

    chunks: list[LegalChunk] = []
    errors: list[str] = []

    for path in paths:
        try:
            document = LegalDocument.model_validate_json(
                path.read_text(encoding="utf-8")
            )
            chunks.extend(
                prepare_legal_document(document)
            )
        except (
            OSError,
            TypeError,
            ValidationError,
            ValueError,
        ) as error:
            errors.append(f"{path.name}: {error}")

    if not chunks:
        raise ValueError(
            "No se generaron segmentos jurídicos."
        )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    output_path.write_text(
        "\n".join(
            json.dumps(
                chunk.model_dump(mode="json"),
                ensure_ascii=False,
            )
            for chunk in chunks
        )
        + "\n",
        encoding="utf-8",
    )

    return chunks, errors