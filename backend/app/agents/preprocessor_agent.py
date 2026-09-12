from pydantic import ValidationError

from app.schemas.contract import ExtractedContract
from app.schemas.preprocessing import (
    PreprocessedContract,
    PreprocessingResponse,
    ProcessedClause,
)
from app.services.semantic_chunking import (
    build_chunk_text,
    build_semantic_chunks,
    find_protected_boundaries,
)
from app.services.text_preprocessor import (
    build_cleaned_document_text,
    clean_contract_sections,
)

MAX_CHUNK_CHARS = 3500
MIN_CHUNK_CHARS = 500


def run_preprocessor_agent(
    contract: ExtractedContract,
) -> PreprocessingResponse:
    """Limpia y segmenta semánticamente un contrato."""

    try:
        cleaned_sections, removed_blocks = clean_contract_sections(contract.sections)

        cleaned_text = build_cleaned_document_text(cleaned_sections)

        chunk_indexes = build_semantic_chunks(
            cleaned_sections,
            max_chunk_chars=MAX_CHUNK_CHARS,
            min_chunk_chars=MIN_CHUNK_CHARS,
        )

        protected_boundaries = find_protected_boundaries(cleaned_sections)

        clauses: list[ProcessedClause] = []

        for order, indexes in enumerate(
            chunk_indexes,
            start=1,
        ):
            first_section = cleaned_sections[indexes[0]]

            content = build_chunk_text(
                cleaned_sections,
                indexes,
                protected_boundaries,
            )

            clauses.append(
                ProcessedClause(
                    order=order,
                    original_order=(first_section.order),
                    heading=(first_section.heading or contract.title),
                    heading_level=(first_section.heading_level or 1),
                    content=content,
                )
            )

        result = PreprocessedContract(
            source_url=contract.source_url,
            platform=contract.platform,
            title=contract.title,
            language=contract.language,
            cleaned_text=cleaned_text,
            clauses=clauses,
            removed_blocks=removed_blocks,
        )

    except (
        TypeError,
        ValidationError,
        ValueError,
        RuntimeError,
    ) as error:
        return PreprocessingResponse(
            status="error",
            error=(f"No se pudo preprocesar el contrato: {error}"),
        )

    return PreprocessingResponse(
        status="success",
        result=result,
    )
