from operator import add, or_
from typing import Annotated, Literal, TypedDict
from uuid import uuid4

from app.schemas.contract import (
    ExtractedContract,
    ExtractionRequest,
)
from app.schemas.legal_analysis import (
    ClauseAnalysisRequest,
    ClauseAnalysisResponse,
)
from app.schemas.legal_corpus import Jurisdiction
from app.schemas.preprocessing import PreprocessedContract

PipelineStatus = Literal[
    "pending",
    "running",
    "success",
    "partial",
    "error",
]

PipelineStep = Literal[
    "extraction",
    "preprocessing",
    "knowledge",
    "legal_analysis",
    "finalization",
]


class PipelineError(TypedDict):
    """Fallo identificado por etapa y, si aplica, cláusula."""

    step: PipelineStep
    clause_order: int | None
    message: str
    attempt: int
    retryable: bool


class ClauseTaskState(TypedDict):
    """Entrada independiente enviada para analizar una cláusula."""

    analysis_request: ClauseAnalysisRequest


class OrchestrationState(TypedDict):
    """Datos compartidos durante una ejecución del pipeline."""

    execution_id: str
    request: ExtractionRequest
    jurisdiction: Jurisdiction
    status: PipelineStatus
    current_step: PipelineStep
    extracted_contract: ExtractedContract | None
    preprocessed_contract: PreprocessedContract | None
    current_clause_index: int
    clause_results: Annotated[
        dict[int, ClauseAnalysisResponse],
        or_,
    ]
    errors: Annotated[list[PipelineError], add]
    attempts: Annotated[dict[str, int], or_]


def create_initial_state(
    request: ExtractionRequest,
    jurisdiction: Jurisdiction = "ecuador",
) -> OrchestrationState:
    """Crea un estado independiente para cada ejecución."""

    return OrchestrationState(
        execution_id=str(uuid4()),
        request=request,
        jurisdiction=jurisdiction,
        status="pending",
        current_step="extraction",
        extracted_contract=None,
        preprocessed_contract=None,
        current_clause_index=0,
        clause_results={},
        errors=[],
        attempts={},
    )
