from typing import Literal, TypedDict
from uuid import uuid4

from app.schemas.contract import (
    ExtractedContract,
    ExtractionRequest,
)
from app.schemas.knowledge import KnowledgeResponse
from app.schemas.legal_analysis import ClauseAnalysisResponse
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
    "record_result",
    "finalization",
]


class PipelineError(TypedDict):
    """Fallo identificado por etapa y, si aplica, cláusula."""

    step: PipelineStep
    clause_order: int | None
    message: str
    attempt: int
    retryable: bool


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
    knowledge_response: KnowledgeResponse | None
    clause_results: dict[int, ClauseAnalysisResponse]
    errors: list[PipelineError]
    attempts: dict[str, int]


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
        knowledge_response=None,
        clause_results={},
        errors=[],
        attempts={},
    )
