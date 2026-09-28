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
        chunk_id="ec_defensa_consumidor_2000_chunk_0048",
        document_id="ec_defensa_consumidor_2000",
        chunk_index=48,
        content=(
            "Son nulas las cláusulas que permiten al "
            "proveedor variar unilateralmente el precio."
        ),
        title="Ley Orgánica de Defensa del Consumidor",
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


def create_execution(
    *,
    evidence_sufficiency: str = "sufficient",
    indices: list[int] | None = None,
) -> ClassificationExecution:
    """Crea una clasificación generada por el modelo."""

    if indices is None:
        indices = [0] if evidence_sufficiency != "insufficient" else []

    return ClassificationExecution(
        decision=ClauseAnalysisDecision(
            category="Modificación de condiciones",
            clause_type="Facultad unilateral del proveedor",
            target="Proveedor",
            consequence=(
                "El precio del servicio puede cambiar para el usuario."
            ),
            classification="strong_indications_of_abusiveness",
            analysis_status="classified",
            justification=(
                "La cláusula presenta indicios fuertes "
                "de modificación unilateral."
            ),
            recommendation="Revisar la facultad unilateral.",
            evidence_sufficiency=evidence_sufficiency,
            legal_basis_indices=indices,
        ),
        model_response=ModelResponse(
            provider="openrouter",
            model="deepseek/deepseek-v4-flash-0731",
            content="{}",
        ),
    )


def create_assessment(
    *,
    evidence_sufficiency: str = "sufficient",
    legal_basis: list[LegalKnowledgeMatch] | None = None,
) -> ClauseAssessment:
    """Crea la valoración jurídica final."""

    if legal_basis is None:
        legal_basis = (
            [create_match()]
            if evidence_sufficiency != "insufficient"
            else []
        )

    return ClauseAssessment(
        category="Modificación de condiciones",
        clause_type="Facultad unilateral del proveedor",
        target="Proveedor",
        consequence=(
            "El precio del servicio puede cambiar para el usuario."
        ),
        classification="strong_indications_of_abusiveness",
        analysis_status="classified",
        relevant_fragment=(
            "El proveedor podrá modificar "
            "unilateralmente el precio del servicio."
        ),
        justification=(
            "La cláusula presenta indicios fuertes "
            "de modificación unilateral."
        ),
        recommendation="Revisar la facultad unilateral.",
        evidence_sufficiency=evidence_sufficiency,
        legal_basis=legal_basis,
    )


def test_builds_query_from_processed_clause() -> None:
    """Construye la búsqueda usando la cláusula real."""

    request = create_request()

    query = legal_analyzer_agent.build_legal_search_query(
        request
    )

    assert request.clause.content in query
    assert request.clause.heading in query
    assert "Jurisdicción:" not in query
    assert "Normativa aplicable" not in query


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
        assert request.clause.content in knowledge_request.query
        assert knowledge_request.top_k == 5

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
        received_request: ClauseAnalysisRequest,
        legal_context: list[LegalKnowledgeMatch],
    ) -> ClauseAssessment:
        assert received_execution == execution
        assert received_request == request
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

    response = legal_analyzer_agent.run_legal_analyzer_agent(
        request
    )

    assert response.status == "success"
    assert response.error is None
    assert response.result == assessment
    assert response.result.classification == (
        "strong_indications_of_abusiveness"
    )


def test_agent_continues_when_knowledge_fails(
    monkeypatch,
) -> None:
    """Clasifica aunque el RAG presente un error técnico."""

    request = create_request()
    execution = create_execution(
        evidence_sufficiency="insufficient"
    )
    assessment = create_assessment(
        evidence_sufficiency="insufficient"
    )

    def fake_knowledge(
        knowledge_request: KnowledgeQuery,
    ) -> KnowledgeResponse:
        return KnowledgeResponse(
            status="error",
            query=knowledge_request.query,
            error="ChromaDB no disponible.",
        )

    def fake_classification(
        received_request: ClauseAnalysisRequest,
        legal_context: list[LegalKnowledgeMatch],
    ) -> ClassificationExecution:
        assert received_request == request
        assert legal_context == []
        return execution

    def fake_grounding(
        received_execution: ClassificationExecution,
        received_request: ClauseAnalysisRequest,
        legal_context: list[LegalKnowledgeMatch],
    ) -> ClauseAssessment:
        assert received_execution == execution
        assert received_request == request
        assert legal_context == []
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

    response = legal_analyzer_agent.run_legal_analyzer_agent(
        request
    )

    assert response.status == "success"
    assert response.error is None
    assert response.result == assessment
    assert response.result.evidence_sufficiency == "insufficient"
    assert response.result.legal_basis == []


def test_agent_continues_without_knowledge_matches(
    monkeypatch,
) -> None:
    """Clasifica aunque el RAG no recupere evidencias."""

    request = create_request()
    execution = create_execution(
        evidence_sufficiency="insufficient"
    )
    assessment = create_assessment(
        evidence_sufficiency="insufficient"
    )

    def fake_knowledge(
        knowledge_request: KnowledgeQuery,
    ) -> KnowledgeResponse:
        return KnowledgeResponse(
            status="success",
            query=knowledge_request.query,
            matches=[],
        )

    def fake_classification(
        received_request: ClauseAnalysisRequest,
        legal_context: list[LegalKnowledgeMatch],
    ) -> ClassificationExecution:
        assert received_request == request
        assert legal_context == []
        return execution

    def fake_grounding(
        received_execution: ClassificationExecution,
        received_request: ClauseAnalysisRequest,
        legal_context: list[LegalKnowledgeMatch],
    ) -> ClauseAssessment:
        assert received_execution == execution
        assert received_request == request
        assert legal_context == []
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

    response = legal_analyzer_agent.run_legal_analyzer_agent(
        request
    )

    assert response.status == "success"
    assert response.error is None
    assert response.result == assessment
    assert response.result.evidence_sufficiency == "insufficient"


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

    response = legal_analyzer_agent.run_legal_analyzer_agent(
        create_request()
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
        request: ClauseAnalysisRequest,
        legal_context: list[LegalKnowledgeMatch],
    ) -> ClauseAssessment:
        raise LegalGroundingError("Fundamento inexistente.")

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

    response = legal_analyzer_agent.run_legal_analyzer_agent(
        create_request()
    )

    assert response.status == "error"
    assert response.result is None
    assert response.error is not None
    assert "Fundamento inexistente" in response.error


def test_agent_uses_received_context_without_new_search(
    monkeypatch,
) -> None:
    """Analiza evidencia recibida sin consultar nuevamente el RAG."""

    request = create_request()
    match = create_match()
    execution = create_execution()
    assessment = create_assessment()

    def fail_knowledge(
        _: KnowledgeQuery,
    ) -> KnowledgeResponse:
        raise AssertionError(
            "No debe consultar nuevamente el RAG."
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
        received_request: ClauseAnalysisRequest,
        legal_context: list[LegalKnowledgeMatch],
    ) -> ClauseAssessment:
        assert received_execution == execution
        assert received_request == request
        assert legal_context == [match]
        return assessment

    monkeypatch.setattr(
        legal_analyzer_agent,
        "run_knowledge_agent",
        fail_knowledge,
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
        legal_analyzer_agent.run_legal_analyzer_with_context(
            request,
            [match],
        )
    )

    assert response.status == "success"
    assert response.error is None
    assert response.result == assessment
