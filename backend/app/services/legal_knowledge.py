import json
import re
from pathlib import Path

from pydantic import ValidationError

from app.schemas.knowledge import LegalChunk
from app.schemas.legal_corpus import LegalDocument

MAX_CHUNK_LENGTH = 1200
CHUNK_OVERLAP = 200

LEGAL_START_PATTERN = re.compile(
    (
        r"^(?=(?:"
        r"Art(?:ículo)?\.?\s+\d+|"
        r"(?:CAP[IÍ]TULO|T[IÍ]TULO|"
        r"SECCI[ÓO]N)\b|"
        r"(?:\d+|[a-z])\.[ \t]"
        r"))"
    ),
    re.MULTILINE | re.IGNORECASE,
)

SENTENCE_END_PATTERN = re.compile(
    r"(?:[;:!?]|(?<!\d)(?<!Art)\.)(?=\s|$)",
    re.IGNORECASE,
)

def find_semantic_end(
    text: str,
    start: int,
    maximum_end: int,
    max_length: int,
) -> int:
    """Localiza el mejor final para un segmento."""

    minimum_end = start + max_length // 2

    legal_boundaries = [
        match.start()
        for match in LEGAL_START_PATTERN.finditer(
            text,
            minimum_end,
            maximum_end,
        )
        if match.start() > start
    ]

    if legal_boundaries:
        return legal_boundaries[-1]

    sentence_boundaries = [
        match.end()
        for match in SENTENCE_END_PATTERN.finditer(
            text,
            minimum_end,
            maximum_end,
        )
    ]

    if sentence_boundaries:
        return sentence_boundaries[-1]

    word_boundary = text.rfind(
        " ",
        minimum_end,
        maximum_end,
    )

    if word_boundary > start:
        return word_boundary

    return maximum_end


def find_semantic_start(
    text: str,
    start: int,
    end: int,
    overlap: int,
) -> int:
    """Inicia el solapamiento en una unidad completa."""

    target = max(
        start + 1,
        end - overlap,
    )
    lower_bound = max(
        start + 1,
        target - overlap,
    )
    candidates = [
        match.start()
        for match in LEGAL_START_PATTERN.finditer(
            text,
            lower_bound,
            end,
        )
        if start < match.start() < end
    ]

    for match in SENTENCE_END_PATTERN.finditer(
        text,
        lower_bound,
        end,
    ):
        candidate = match.end()

        while (
            candidate < end
            and text[candidate].isspace()
        ):
            candidate += 1

        if start < candidate < end:
            candidates.append(candidate)

    if candidates:
        return min(
            set(candidates),
            key=lambda candidate: (
                abs(candidate - target),
                candidate,
            ),
        )

    next_start = target

    while (
        next_start < end
        and next_start > 0
        and not text[next_start - 1].isspace()
    ):
        next_start += 1

    return next_start

def split_legal_text(
    text: str,
    max_length: int = MAX_CHUNK_LENGTH,
    overlap: int = CHUNK_OVERLAP,
) -> list[str]:
    """Divide texto jurídico por unidades semánticas."""

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
            end = find_semantic_end(
                normalized,
                start,
                maximum_end,
                max_length,
            )

        chunk = normalized[start:end].strip()

        if chunk and (
            not chunks or chunk != chunks[-1]
        ):
            chunks.append(chunk)

        if end >= len(normalized):
            break

        next_start = find_semantic_start(
            normalized,
            start,
            end,
            overlap,
        )
        start = max(
            next_start,
            start + 1,
        )

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