import json

import pytest
from app.llm.models import (
    ChatMessage,
    ModelProviderError,
    ModelResponse,
)
from app.schemas.knowledge import LegalKnowledgeMatch
from app.schemas.legal_analysis import (
    ClauseAnalysisRequest,
)
from app.schemas.preprocessing import ProcessedClause
from app.services import analysis


def create_request() -> ClauseAnalysisRequest:
    """Crea una solicitud de clasificación."""

    return ClauseAnalysisRequest(
        source_url="https://example.com/terms",
        platform="Example SaaS",
        language="es",
        jurisdiction="ecuador",
        clause=ProcessedClause(
            order=1,
            original_order=4,
            heading="Limitación de responsabilidad",
            heading_level=2,
            content=(
                "El proveedor no será responsable por "
                "ningún daño causado al usuario."
            ),
        ),
    )


def create_match() -> LegalKnowledgeMatch:
    """Crea evidencia jurídica para la clasificación."""

    return LegalKnowledgeMatch(
        chunk_id=(
            "ec_defensa_consumidor_2000_chunk_0048"
        ),
        document_id="ec_defensa_consumidor_2000",
        chunk_index=48,
        content=(
            "Son nulas las cláusulas que limiten la "
            "responsabilidad del proveedor."
        ),
        title=(
            "Ley Orgánica de Defensa del Consumidor"
        ),
        jurisdiction="ecuador",
        issuing_body="Congreso Nacional del Ecuador",
        document_type="law",
        binding_level="binding",
        status="amended",
        language="es",
        source_url="https://example.com/consumer-law",
        official_citation=(
            "Suplemento del Registro Oficial 116"
        ),
        topics="consumidores|cláusulas abusivas",
        checksum="a" * 64,
        distance=0.18,
    )


def create_decision_payload() -> dict[str, object]:
    """Crea una decisión estructurada válida."""

    return {
        "category": "limitation_of_liability",
        "classification": "abusive",
        "analysis_status": "classified",
        "relevant_fragment": (
            "El proveedor no será responsable"
        ),
        "justification": (
            "La cláusula excluye ampliamente la "
            "responsabilidad del proveedor."
        ),
        "recommendation": (
            "Solicitar revisión jurídica."
        ),
        "evidence_sufficiency": "sufficient",
        "legal_basis_indices": [0],
    }


def create_model_response(
    payload: dict[str, object],
) -> ModelResponse:
    """Simula una respuesta estructurada del modelo."""

    return ModelResponse(
        provider="ollama",
        model="qwen3:4b",
        content=json.dumps(
            payload,
            ensure_ascii=False,
        ),
        prompt_tokens=120,
        completion_tokens=80,
    )


def configure_model_response(
    monkeypatch,
    payload: dict[str, object],
) -> None:
    """Configura una respuesta simulada del gateway."""

    def fake_model(
        messages: list[ChatMessage],
        response_schema: dict[str, object] | None,
    ) -> ModelResponse:
        assert len(messages) == 2
        assert messages[0].role == "system"
        assert messages[1].role == "user"
        assert response_schema is not None

        return create_model_response(payload)

    monkeypatch.setattr(
        analysis,
        "generate_model_response",
        fake_model,
    )


def test_classify_clause_returns_valid_decision(
    monkeypatch,
) -> None:
    """Clasifica y conserva los datos del modelo."""

    configure_model_response(
        monkeypatch,
        create_decision_payload(),
    )

    execution = analysis.classify_clause(
        create_request(),
        [create_match()],
    )

    assert (
        execution.decision.classification
        == "abusive"
    )
    assert execution.decision.legal_basis_indices == [0]
    assert execution.model_response.provider == "ollama"
    assert execution.model_response.prompt_tokens == 120


def test_classification_allows_review_without_evidence(
    monkeypatch,
) -> None:
    """Permite abstenerse cuando falta evidencia."""

    payload = {
        "category": "other_contractual_risk",
        "classification": None,
        "analysis_status": "requires_review",
        "relevant_fragment": (
            "El proveedor no será responsable"
        ),
        "justification": (
            "No existe evidencia jurídica suficiente."
        ),
        "recommendation": (
            "Solicitar revisión jurídica."
        ),
        "evidence_sufficiency": "insufficient",
        "legal_basis_indices": [],
    }
    configure_model_response(monkeypatch, payload)

    execution = analysis.classify_clause(
        create_request(),
        [],
    )

    assert execution.decision.classification is None
    assert (
        execution.decision.analysis_status
        == "requires_review"
    )


def test_classification_rejects_invalid_json(
    monkeypatch,
) -> None:
    """Controla una respuesta que no contiene JSON."""

    def fake_model(
        messages: list[ChatMessage],
        response_schema: dict[str, object] | None,
    ) -> ModelResponse:
        return ModelResponse(
            provider="ollama",
            model="qwen3:4b",
            content="respuesta no estructurada",
        )

    monkeypatch.setattr(
        analysis,
        "generate_model_response",
        fake_model,
    )

    with pytest.raises(
        analysis.ClauseClassificationError,
        match="clasificación inválida",
    ):
        analysis.classify_clause(
            create_request(),
            [create_match()],
        )


def test_classification_rejects_unknown_evidence(
    monkeypatch,
) -> None:
    """Rechaza índices que no existen en el contexto."""

    payload = create_decision_payload()
    payload["legal_basis_indices"] = [1]
    configure_model_response(monkeypatch, payload)

    with pytest.raises(
        analysis.ClauseClassificationError,
        match="índice jurídico inexistente",
    ):
        analysis.classify_clause(
            create_request(),
            [create_match()],
        )


def test_classification_rejects_duplicate_evidence(
    monkeypatch,
) -> None:
    """Rechaza el uso duplicado de una evidencia."""

    payload = create_decision_payload()
    payload["legal_basis_indices"] = [0, 0]
    configure_model_response(monkeypatch, payload)

    with pytest.raises(
        analysis.ClauseClassificationError,
        match="duplicados",
    ):
        analysis.classify_clause(
            create_request(),
            [create_match()],
        )


def test_classification_rejects_invented_fragment(
    monkeypatch,
) -> None:
    """Impide justificar con un fragmento inexistente."""

    payload = create_decision_payload()
    payload["relevant_fragment"] = (
        "El usuario renuncia a todos sus derechos."
    )
    configure_model_response(monkeypatch, payload)

    with pytest.raises(
        analysis.ClauseClassificationError,
        match="no pertenece",
    ):
        analysis.classify_clause(
            create_request(),
            [create_match()],
        )


def test_classification_controls_provider_error(
    monkeypatch,
) -> None:
    """Convierte los fallos del proveedor en error controlado."""

    def fail_model(
        messages: list[ChatMessage],
        response_schema: dict[str, object] | None,
    ) -> ModelResponse:
        raise ModelProviderError(
            "Proveedor no disponible."
        )

    monkeypatch.setattr(
        analysis,
        "generate_model_response",
        fail_model,
    )

    with pytest.raises(
        analysis.ClauseClassificationError,
        match="proveedor de lenguaje",
    ):
        analysis.classify_clause(
            create_request(),
            [create_match()],
        )