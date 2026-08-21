from pydantic import ValidationError

from app.schemas.contract import ExtractedContract
from app.schemas.preprocessing import (
    PreprocessedContract,
    PreprocessingResponse,
)
from app.services.text_preprocessor import (
    build_cleaned_text,
    clean_contract_sections,
    segment_contract_sections,
)


def run_preprocessor_agent(
    contract: ExtractedContract,
) -> PreprocessingResponse:
    """Limpia y segmenta un contrato mediante reglas estructurales."""

    try:
        cleaned_sections, removed_blocks = (
            clean_contract_sections(contract.sections)
        )

        clauses = segment_contract_sections(
            cleaned_sections,
            default_heading=contract.title,
            default_heading_level=1,
        )

        if not clauses:
            raise ValueError(
                "No se encontraron cláusulas contractuales."
            )

        cleaned_text = build_cleaned_text(clauses)

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
