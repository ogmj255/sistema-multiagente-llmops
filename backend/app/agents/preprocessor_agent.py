from pydantic import ValidationError

from app.schemas.contract import ExtractedContract
from app.schemas.preprocessing import (
    PreprocessedContract,
    PreprocessingResponse,
    ProcessedClause,
)
from app.services.semantic_chunking import (
    build_semantic_chunks,
)
from app.services.text_preprocessor import (
    build_cleaned_document_text,
    clean_contract_sections,
    parse_contract_html,
)

BREAKPOINT_PERCENTILE = 80.0
BUFFER_SIZE = 1


def run_preprocessor_agent(
    contract: ExtractedContract,
) -> PreprocessingResponse:
    """Limpia HTML y segmenta semanticamente el contrato."""

    try:
        (
            title,
            language,
            extracted_sections,
        ) = parse_contract_html(
            contract.raw_html
        )

        (
            cleaned_sections,
            removed_blocks,
        ) = clean_contract_sections(
            extracted_sections
        )

        cleaned_text = build_cleaned_document_text(
            cleaned_sections
        )

        semantic_chunks = build_semantic_chunks(
            cleaned_text,
            breakpoint_percentile=(
                BREAKPOINT_PERCENTILE
            ),
            buffer_size=BUFFER_SIZE,
        )

        clauses = [
            ProcessedClause(
                order=order,
                original_order=order,
                heading=None,
                heading_level=None,
                content=chunk,
            )
            for order, chunk in enumerate(
                semantic_chunks,
                start=1,
            )
        ]

        result = PreprocessedContract(
            source_url=contract.source_url,
            platform=contract.platform,
            title=title,
            language=language,
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
            error=(
                "No se pudo preprocesar el contrato: "
                f"{error}"
            ),
        )

    return PreprocessingResponse(
        status="success",
        result=result,
    )
