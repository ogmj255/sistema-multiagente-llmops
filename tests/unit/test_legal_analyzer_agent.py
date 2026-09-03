from app.agents import legal_analyzer_agent
from app.llm.models import ModelResponse
from app.schemas.knowledge import (
    KnowledgeQuery,
    KnowledgeResponse,
    LegalKnowledgeMatch,
)
from app.schemas.legal_analysis import (
    ClauseAnalysisDecision,
    ClauseAnalysisRequest,
    ClauseAssessment,
)
from app.schemas.preprocessing import ProcessedClause
from app.services.analysis import (
    ClassificationExecution,
    ClauseClassificationError,
    LegalGroundingError,
)


def create_request() -> ClauseAnalysisRequest:
    """Crea una solicitud válida para el agente."""

    return ClauseAnalysisRequest(
        source_url="https://example.com/terms",
        platform="Example SaaS",
        language="es",
        jurisdiction="ecuador",
        clause=ProcessedClause(
            order=1,
            original_order=8,
            heading="Modificación unilateral",
            heading_level=2,
            content=(
                "El proveedor podrá modificar "
                "unilateralmente el precio del servicio."
            ),
        ),
    )


def create_match() -> LegalKnowledgeMatch:
    """Crea evidencia jurídica recuperada."""

    return LegalKnowledgeMatch(
        chunk_id=(
            "ec_defensa_consumidor_2000_chunk_0048"
        ),
        document_id="ec_defensa_consumidor_2000",
        chunk_index=48,
        content=(
            "Son nulas las cláusulas que permiten al "
            "proveedor variar unilateralmente el precio."
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
        official_citation="Registro Oficial 116",
        topics="consumidores|contratos",
        checksum="a" * 64,
        distance=0.18,
    )


def create_execution() -> ClassificationExecution:
    """Crea una clasificación respaldada."""

    return ClassificationExecution(
        decision=ClauseAnalysisDecision(
            category="unilateral_modification",
            classification="abusive",
            analysis_status="classified",
            relevant_fragment=(
                "El proveedor podrá modificar "
                "unilateralmente el precio del servicio."
            ),
            justification=(
                "La cláusula permite una modificación "
                "unilateral prohibida."
            ),
            recommendation=(
                "Eliminar la facultad unilateral."
            ),
            evidence_sufficiency="sufficient",
            legal_basis_indices=[0],
        ),
        model_response=ModelResponse(
            provider="ollama",
            model="qwen3:4b",
            content="{}",
        ),
    )


def create_assessment() -> ClauseAssessment:
    """Crea la valoración jurídica final."""

    return ClauseAssessment(
        category="unilateral_modification",
        classification="abusive",
        analysis_status="classified",
        relevant_fragment=(
            "El proveedor podrá modificar "
            "unilateralmente el precio del servicio."
        ),
        justification=(
            "La cláusula permite una modificación "
            "unilateral prohibida."
        ),
        recommendation=(
            "Eliminar la facultad unilateral."
        ),
        evidence_sufficiency="sufficient",
        legal_basis=[create_match()],
    )


def test_builds_query_from_processed_clause() -> None:
    """Construye la búsqueda usando la cláusula real."""

    request = create_request()

    query = (
        legal_analyzer_agent.build_legal_search_query(
            request
        )
    )

    assert request.clause.content in query
    assert request.clause.heading in query
    assert request.jurisdiction in query
    assert "términos de servicio SaaS" in query


def test_agent_runs_complete_analysis(
    monkeypatch,
) -> None:
    """Coordina RAG, clasificación y fundamentación."""

    request = create_request()
    match = create_match()
    execution = create_execution()
    assessment = create_assessment()

    def fake_knowledge(
        knowledge_request: KnowledgeQuery,
    ) -> KnowledgeResponse:
        assert request.clause.content in (
            knowledge_request.query
        )
        assert knowledge_request.top_k == 5
        assert (
            knowledge_request.jurisdiction
            == "ecuador"
        )

        return KnowledgeResponse(
            status="success",
            query=knowledge_request.query,
            matches=[match],
        )

    def fake_classification(
        received_request: ClauseAnalysisRequest,
        legal_context: list[LegalKnowledgeMatch],
    ) -> ClassificationExecution:
        assert received_request == request
        assert legal_context == [match]
        return execution

    def fake_grounding(
        received_execution: ClassificationExecution,
        legal_context: list[LegalKnowledgeMatch],
    ) -> ClauseAssessment:
        assert received_execution == execution
        assert legal_context == [match]
        return assessment

    monkeypatch.setattr(
        legal_analyzer_agent,
        "run_knowledge_agent",
        fake_knowledge,
    )
    monkeypatch.setattr(
        legal_analyzer_agent,
        "classify_clause",
        fake_classification,
    )
    monkeypatch.setattr(
        legal_analyzer_agent,
        "build_grounded_assessment",
        fake_grounding,
    )

    response = (
        legal_analyzer_agent
        .run_legal_analyzer_agent(request)
    )

    assert response.status == "success"
    assert response.error is None
    assert response.result == assessment
    assert response.result.risk_level == "high"


def test_agent_controls_knowledge_error(
    monkeypatch,
) -> None:
    """Detiene el flujo si falla el RAG."""

    def fake_knowledge(
        request: KnowledgeQuery,
    ) -> KnowledgeResponse:
        return KnowledgeResponse(
            status="error",
            query=request.query,
            error="ChromaDB no disponible.",
        )

    monkeypatch.setattr(
        legal_analyzer_agent,
        "run_knowledge_agent",
        fake_knowledge,
    )

    response = (
        legal_analyzer_agent
        .run_legal_analyzer_agent(
            create_request()
        )
    )

    assert response.status == "error"
    assert response.result is None
    assert response.error is not None
    assert "ChromaDB no disponible" in response.error


def test_agent_rejects_empty_knowledge(
    monkeypatch,
) -> None:
    """Controla una recuperación sin evidencias."""

    def fake_knowledge(
        request: KnowledgeQuery,
    ) -> KnowledgeResponse:
        return KnowledgeResponse(
            status="success",
            query=request.query,
        )

    monkeypatch.setattr(
        legal_analyzer_agent,
        "run_knowledge_agent",
        fake_knowledge,
    )

    response = (
        legal_analyzer_agent
        .run_legal_analyzer_agent(
            create_request()
        )
    )

    assert response.status == "error"
    assert response.result is None
    assert response.error is not None
    assert "no recuperó evidencia" in response.error


def test_agent_controls_classification_error(
    monkeypatch,
) -> None:
    """Controla una salida inválida del modelo."""

    match = create_match()

    def fake_knowledge(
        request: KnowledgeQuery,
    ) -> KnowledgeResponse:
        return KnowledgeResponse(
            status="success",
            query=request.query,
            matches=[match],
        )

    def fail_classification(
        request: ClauseAnalysisRequest,
        legal_context: list[LegalKnowledgeMatch],
    ) -> ClassificationExecution:
        raise ClauseClassificationError(
            "Respuesta JSON inválida."
        )

    monkeypatch.setattr(
        legal_analyzer_agent,
        "run_knowledge_agent",
        fake_knowledge,
    )
    monkeypatch.setattr(
        legal_analyzer_agent,
        "classify_clause",
        fail_classification,
    )

    response = (
        legal_analyzer_agent
        .run_legal_analyzer_agent(
            create_request()
        )
    )

    assert response.status == "error"
    assert response.error is not None
    assert "Respuesta JSON inválida" in response.error


def test_agent_controls_grounding_error(
    monkeypatch,
) -> None:
    """Controla una fundamentación incoherente."""

    match = create_match()

    def fake_knowledge(
        request: KnowledgeQuery,
    ) -> KnowledgeResponse:
        return KnowledgeResponse(
            status="success",
            query=request.query,
            matches=[match],
        )

    def fake_classification(
        request: ClauseAnalysisRequest,
        legal_context: list[LegalKnowledgeMatch],
    ) -> ClassificationExecution:
        return create_execution()

    def fail_grounding(
        execution: ClassificationExecution,
        legal_context: list[LegalKnowledgeMatch],
    ) -> ClauseAssessment:
        raise LegalGroundingError(
            "Fundamento inexistente."
        )

    monkeypatch.setattr(
        legal_analyzer_agent,
        "run_knowledge_agent",
        fake_knowledge,
    )
    monkeypatch.setattr(
        legal_analyzer_agent,
        "classify_clause",
        fake_classification,
    )
    monkeypatch.setattr(
        legal_analyzer_agent,
        "build_grounded_assessment",
        fail_grounding,
    )

    response = (
        legal_analyzer_agent
        .run_legal_analyzer_agent(
            create_request()
        )
    )

    assert response.status == "error"
    assert response.result is None
    assert response.error is not None
    assert "Fundamento inexistente" in response.error