from collections.abc import Callable
from datetime import UTC, datetime

from app.agents import orquestador
from app.agents.orquestador import (
    AgenteOrquestador,
    NodosOrquestacion,
)
from app.schemas.contract import (
    ContractSection,
    ExtractedContract,
    ExtractionRequest,
    ExtractionResponse,
)
from app.schemas.knowledge import LegalKnowledgeMatch
from app.schemas.legal_analysis import (
    ClauseAnalysisResponse,
    ClauseAssessment,
)
from app.schemas.orquestacion import (
    OrchestrationState,
    PipelineStatus,
    PipelineStep,
    create_initial_state,
)
from app.schemas.preprocessing import (
    PreprocessedContract,
    PreprocessingResponse,
    ProcessedClause,
)


def crear_nodo(
    nombre: str,
    etapa: PipelineStep,
    ejecutados: list[str],
    estado: PipelineStatus = "running",
) -> Callable[[OrchestrationState], dict[str, object]]:
    def ejecutar(
        _: OrchestrationState,
    ) -> dict[str, object]:
        ejecutados.append(nombre)

        return {
            "status": estado,
            "current_step": etapa,
        }

    return ejecutar


def crear_orquestador_controlado(
    ejecutados: list[str],
) -> AgenteOrquestador:
    nodos = NodosOrquestacion(
        extraer=crear_nodo(
            "extraer",
            "preprocessing",
            ejecutados,
        ),
        preprocesar=crear_nodo(
            "preprocesar",
            "legal_analysis",
            ejecutados,
        ),
        analizar_clausula=crear_nodo(
            "analizar_clausula",
            "record_result",
            ejecutados,
        ),
        registrar_resultado=crear_nodo(
            "registrar_resultado",
            "finalization",
            ejecutados,
        ),
        finalizar=crear_nodo(
            "finalizar",
            "finalization",
            ejecutados,
            estado="success",
        ),
    )

    def decidir_ruta(
        _: OrchestrationState,
    ) -> str:
        return "finalizar"

    return AgenteOrquestador(
        nodos=nodos,
        enrutador=decidir_ruta,
    )


def crear_estado() -> OrchestrationState:
    request = ExtractionRequest(
        url="https://example.com/terms",
        platform="Example",
    )

    return create_initial_state(request)


def crear_contrato_extraido() -> ExtractedContract:
    return ExtractedContract(
        source_url="https://example.com/terms",
        platform="Example",
        title="Terms",
        retrieved_at=datetime.now(UTC),
        extraction_method="beautiful_soup",
        language="es",
        sections=[
            ContractSection(
                order=1,
                heading="Condiciones",
                heading_level=1,
                content="Contenido contractual.",
            ),
        ],
        full_text="Contenido contractual.",
    )


def crear_contrato_preprocesado() -> PreprocessedContract:
    return PreprocessedContract(
        source_url="https://example.com/terms",
        platform="Example",
        title="Terms",
        language="es",
        cleaned_text=(
            "Primera cláusula. Segunda cláusula."
        ),
        clauses=[
            ProcessedClause(
                order=1,
                original_order=1,
                heading="Primera",
                heading_level=2,
                content="Primera cláusula.",
            ),
            ProcessedClause(
                order=2,
                original_order=2,
                heading="Segunda",
                heading_level=2,
                content="Segunda cláusula.",
            ),
        ],
        removed_blocks=[],
    )


def crear_respuesta_legal() -> ClauseAnalysisResponse:
    evidencia = LegalKnowledgeMatch.model_construct()

    valoracion = ClauseAssessment(
        category="other_contractual_risk",
        classification="fair",
        analysis_status="classified",
        relevant_fragment="cláusula",
        justification="No se identificó un riesgo.",
        recommendation="Mantener la redacción.",
        evidence_sufficiency="sufficient",
        legal_basis=[evidencia],
    )

    return ClauseAnalysisResponse(
        status="success",
        result=valoracion,
    )


def test_orquestador_compila_todos_los_nodos():
    grafo = crear_orquestador_controlado(
        []
    ).construir()

    nodos_esperados = {
        "extraer",
        "preprocesar",
        "analizar_clausula",
        "registrar_resultado",
        "finalizar",
    }

    assert nodos_esperados.issubset(grafo.nodes)


def test_orquestador_ejecuta_el_flujo_definido():
    ejecutados: list[str] = []

    grafo = crear_orquestador_controlado(
        ejecutados
    ).construir()

    resultado = grafo.invoke(crear_estado())

    assert ejecutados == [
        "extraer",
        "preprocesar",
        "analizar_clausula",
        "registrar_resultado",
        "finalizar",
    ]
    assert resultado["status"] == "success"


def test_coordina_los_agentes_secuencialmente(
    monkeypatch,
):
    llamadas: list[str] = []

    def extraer(request):
        llamadas.append("web_scraper")

        return ExtractionResponse(
            status="success",
            contract=crear_contrato_extraido(),
        )

    def preprocesar(contract):
        llamadas.append("preprocesador")

        return PreprocessingResponse(
            status="success",
            result=crear_contrato_preprocesado(),
        )

    def analizar(request):
        llamadas.append(
            f"analizador:{request.clause.order}"
        )

        return crear_respuesta_legal()

    monkeypatch.setattr(
        orquestador,
        "run_web_scraper_agent",
        extraer,
    )
    monkeypatch.setattr(
        orquestador,
        "run_preprocessor_agent",
        preprocesar,
    )
    monkeypatch.setattr(
        orquestador,
        "run_legal_analyzer_agent",
        analizar,
    )

    resultado = orquestador.ejecutar_orquestacion(
        ExtractionRequest(
            url="https://example.com/terms",
            platform="Example",
        )
    )

    assert llamadas == [
        "web_scraper",
        "preprocesador",
        "analizador:1",
        "analizador:2",
    ]
    assert resultado["current_clause_index"] == 2
    assert set(resultado["clause_results"]) == {
        1,
        2,
    }
    assert resultado["status"] == "success"
