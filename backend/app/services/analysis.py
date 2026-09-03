from dataclasses import dataclass

from pydantic import ValidationError

from app.llm.model_gateway import (
    generate_model_response,
)
from app.llm.models import (
    ModelProviderError,
    ModelResponse,
)
from app.prompts.legal_analysis import (
    build_legal_analysis_messages,
    get_legal_analysis_response_schema,
)
from app.schemas.knowledge import LegalKnowledgeMatch
from app.schemas.legal_analysis import (
    ClauseAnalysisDecision,
    ClauseAnalysisRequest,
)


class ClauseClassificationError(RuntimeError):
    """Indica que una cláusula no pudo clasificarse."""


@dataclass(frozen=True, slots=True)
class ClassificationExecution:
    """Conserva la decisión y los datos del modelo."""

    decision: ClauseAnalysisDecision
    model_response: ModelResponse


def normalize_comparison_text(text: str) -> str:
    """Normaliza espacios y mayúsculas para comparar textos."""

    return " ".join(text.split()).casefold()


def validate_model_decision(
    decision: ClauseAnalysisDecision,
    request: ClauseAnalysisRequest,
    legal_context: list[LegalKnowledgeMatch],
) -> None:
    """Contrasta la decisión con la entrada original."""

    normalized_fragment = normalize_comparison_text(
        decision.relevant_fragment
    )
    normalized_clause = normalize_comparison_text(
        request.clause.content
    )

    if normalized_fragment not in normalized_clause:
        raise ValueError(
            "El fragmento relevante no pertenece "
            "a la cláusula analizada."
        )

    selected_indices = decision.legal_basis_indices

    if len(selected_indices) != len(
        set(selected_indices)
    ):
        raise ValueError(
            "La decisión contiene índices jurídicos "
            "duplicados."
        )

    invalid_indices = [
        index
        for index in selected_indices
        if index >= len(legal_context)
    ]

    if invalid_indices:
        raise ValueError(
            "La decisión contiene un índice jurídico "
            "inexistente."
        )


def classify_clause(
    request: ClauseAnalysisRequest,
    legal_context: list[LegalKnowledgeMatch],
) -> ClassificationExecution:
    """Clasifica una cláusula mediante el modelo configurado."""

    messages = build_legal_analysis_messages(
        request,
        legal_context,
    )
    response_schema = (
        get_legal_analysis_response_schema()
    )

    try:
        model_response = generate_model_response(
            messages,
            response_schema,
        )
    except ModelProviderError as error:
        raise ClauseClassificationError(
            "El proveedor de lenguaje no pudo "
            f"clasificar la cláusula: {error}"
        ) from error

    try:
        decision = (
            ClauseAnalysisDecision.model_validate_json(
                model_response.content
            )
        )
        validate_model_decision(
            decision,
            request,
            legal_context,
        )
    except (
        TypeError,
        ValidationError,
        ValueError,
    ) as error:
        raise ClauseClassificationError(
            "El modelo devolvió una clasificación "
            f"inválida: {error}"
        ) from error

    return ClassificationExecution(
        decision=decision,
        model_response=model_response,
    )