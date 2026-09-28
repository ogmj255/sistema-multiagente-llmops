import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import partial
from time import perf_counter
from typing import Literal, TypeAlias, TypeVar

from langgraph.errors import NodeError
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, RetryPolicy, Send
from pydantic import ValidationError

from app.agents.legal_analyzer_agent import (
    LEGAL_CONTEXT_RESULTS,
    build_legal_search_query,
)
from app.agents.observability_agent import build_observability_summary
from app.core.observability import (
    get_current_trace_context,
    observe_agent,
    start_pipeline_observation,
    update_pipeline_observation,
)
from app.mcp.registry import ClienteMCP
from app.schemas.contract import (
    ExtractionRequest,
    ExtractionResponse,
)
from app.schemas.knowledge import KnowledgeResponse
from app.schemas.legal_analysis import (
    ClauseAnalysisRequest,
    ClauseAnalysisResponse,
)
from app.schemas.observability import (
    LegalAnalyzerToolResponse,
    LLMInvocationMetrics,
    ObservabilitySummary,
)
from app.schemas.orchestration import (
    ClauseTaskState,
    OrchestrationState,
    PipelineStatus,
    PipelineStep,
    create_initial_state,
)
from app.schemas.preprocessing import PreprocessingResponse
from app.schemas.report import (
    AnalysisReport,
    ClauseReportItem,
    ReportGenerationRequest,
    ReportGenerationResponse,
)
from app.services.analysis_persistence import (
    calculate_content_hash,
    find_successful_analysis,
    save_analysis,
)
from app.services.observability_persistence import (
    save_observability_run,
)

logger = logging.getLogger(__name__)


ActualizacionEstado: TypeAlias = dict[str, object]

NodoPipeline: TypeAlias = Callable[
    [OrchestrationState],
    ActualizacionEstado | Awaitable[ActualizacionEstado],
]

NodoClausula: TypeAlias = Callable[
    [ClauseTaskState],
    ActualizacionEstado | Awaitable[ActualizacionEstado],
]

DecisionRuta = Literal[
    "continuar",
    "finalizar",
]

DistribucionClausulas: TypeAlias = list[Send] | Literal["finalizar"]

EnrutadorClausulas: TypeAlias = Callable[
    [OrchestrationState],
    DistribucionClausulas,
]

ResultadoOperacion = TypeVar("ResultadoOperacion")
OperacionAsincrona: TypeAlias = Callable[
    [],
    Awaitable[ResultadoOperacion],
]

MAX_INTENTOS = 2
MAX_CLAUSULAS_CONCURRENTES = 1

POLITICA_REINTENTOS = RetryPolicy(
    max_attempts=MAX_INTENTOS,
    jitter=False,
    retry_on=RuntimeError,
)

ETAPA_POR_NODO: dict[str, PipelineStep] = {
    "extraer": "extraction",
    "preprocesar": "preprocessing",
    "generar_informe": "report_generation",
}


def manejar_error_nodo(
    _state: OrchestrationState,
    error: NodeError,
) -> Command[Literal["finalizar"]]:
    """Registra un error global después de agotar los intentos."""

    if not isinstance(error.error, RuntimeError):
        raise error.error

    etapa = ETAPA_POR_NODO[error.node]

    return Command(
        update={
            "status": "error",
            "current_step": etapa,
            "errors": [
                {
                    "step": etapa,
                    "clause_order": None,
                    "message": str(error.error),
                    "attempt": MAX_INTENTOS,
                    "retryable": False,
                }
            ],
            "attempts": {
                etapa: MAX_INTENTOS,
            },
        },
        goto="finalizar",
    )


@dataclass(frozen=True)
class NodosOrquestacion:
    """Funciones que ejecutará el grafo."""

    extraer: NodoPipeline
    preprocesar: NodoPipeline
    verificar_analisis_previo: NodoPipeline
    procesar_clausula: NodoClausula
    generar_informe: NodoPipeline
    finalizar: NodoPipeline


class AgenteOrquestador:
    """Construye el flujo multiagente mediante LangGraph."""

    def __init__(
        self,
        nodos: NodosOrquestacion,
        distribuidor: EnrutadorClausulas,
    ) -> None:
        self._nodos = nodos
        self._distribuidor = distribuidor

    def construir(self):
        """Construye y compila el grafo."""

        grafo = StateGraph(OrchestrationState)

        grafo.add_node(
            "extraer",
            self._nodos.extraer,
            retry_policy=POLITICA_REINTENTOS,
            error_handler=manejar_error_nodo,
        )
        grafo.add_node(
            "preprocesar",
            self._nodos.preprocesar,
            retry_policy=POLITICA_REINTENTOS,
            error_handler=manejar_error_nodo,
        )
        grafo.add_node(
            "verificar_analisis_previo",
            self._nodos.verificar_analisis_previo,
        )
        grafo.add_node(
            "procesar_clausula",
            self._nodos.procesar_clausula,
        )
        grafo.add_node(
            "generar_informe",
            self._nodos.generar_informe,
            retry_policy=POLITICA_REINTENTOS,
            error_handler=manejar_error_nodo,
        )
        grafo.add_node(
            "finalizar",
            self._nodos.finalizar,
        )

        grafo.add_edge(START, "extraer")

        grafo.add_conditional_edges(
            "extraer",
            decidir_continuacion,
            {
                "continuar": "preprocesar",
                "finalizar": "finalizar",
            },
        )

        grafo.add_edge(
            "preprocesar",
            "verificar_analisis_previo",
        )

        grafo.add_conditional_edges(
            "verificar_analisis_previo",
            self._distribuidor,
            [
                "procesar_clausula",
                "finalizar",
            ],
        )

        grafo.add_edge(
            "procesar_clausula",
            "generar_informe",
        )
        grafo.add_edge(
            "generar_informe",
            "finalizar",
        )
        grafo.add_edge("finalizar", END)

        return grafo.compile()


async def ejecutar_con_reintentos(
    operacion: OperacionAsincrona[ResultadoOperacion],
) -> ResultadoOperacion:
    """Reintenta una operación MCP sin repetir etapas anteriores."""

    ultimo_error: RuntimeError | None = None

    for _ in range(MAX_INTENTOS):
        try:
            return await operacion()
        except RuntimeError as error:
            ultimo_error = error

    if ultimo_error is None:
        raise RuntimeError("La operación MCP no pudo ejecutarse.")

    raise ultimo_error


def crear_actualizacion_error_clausula(
    etapa: Literal["knowledge", "legal_analysis"],
    orden_clausula: int,
    error: RuntimeError,
) -> ActualizacionEstado:
    """Construye el resultado de un fallo aislado por cláusula."""

    mensaje = str(error)

    return {
        "clause_results": {
            orden_clausula: ClauseAnalysisResponse(
                status="error",
                error=mensaje,
            )
        },
        "errors": [
            {
                "step": etapa,
                "clause_order": orden_clausula,
                "message": mensaje,
                "attempt": MAX_INTENTOS,
                "retryable": False,
            }
        ],
        "attempts": {
            f"{etapa}:{orden_clausula}": MAX_INTENTOS,
        },
    }


@observe_agent("web-scraper")
async def extraer_contrato(
    state: OrchestrationState,
    cliente: ClienteMCP,
) -> ActualizacionEstado:
    """Ejecuta el Agente Web Scraper mediante MCP."""

    contenido = await cliente.invocar(
        "extractor_web",
        state["request"].model_dump(mode="json"),
    )

    try:
        respuesta = ExtractionResponse.model_validate(contenido)
    except ValidationError as error:
        raise RuntimeError(
            "El Agente Web Scraper devolvió una respuesta inválida."
        ) from error

    if respuesta.status == "error" or respuesta.contract is None:
        raise RuntimeError(respuesta.error or "No se pudo extraer el contrato.")

    return {
        "status": "running",
        "current_step": "preprocessing",
        "extracted_contract": respuesta.contract,
    }


@observe_agent("preprocessor")
async def preprocesar_contrato(
    state: OrchestrationState,
    cliente: ClienteMCP,
) -> ActualizacionEstado:
    """Ejecuta el Agente Preprocesador mediante MCP."""

    contrato = state["extracted_contract"]

    if contrato is None:
        raise RuntimeError("No existe un contrato para preprocesar.")

    contenido = await cliente.invocar(
        "preprocesador",
        {"contract": contrato.model_dump(mode="json")},
    )

    try:
        respuesta = PreprocessingResponse.model_validate(contenido)
    except ValidationError as error:
        raise RuntimeError(
            "El Agente Preprocesador devolvió una respuesta inválida."
        ) from error

    if respuesta.status == "error" or respuesta.result is None:
        raise RuntimeError(respuesta.error or "No se pudo preprocesar el contrato.")

    return {
        "current_step": "knowledge",
        "preprocessed_contract": respuesta.result,
    }


def verificar_analisis_previo(
    state: OrchestrationState,
) -> ActualizacionEstado:
    """Busca una ejecuci?n exitosa de la misma versi?n contractual."""

    contrato = state["preprocessed_contract"]

    if contrato is None:
        raise RuntimeError(
            "No existe un contrato preprocesado para verificar."
        )

    content_hash = calculate_content_hash(
        contrato.cleaned_text
    )

    registro = find_successful_analysis(
        str(contrato.source_url),
        content_hash,
    )

    if registro is None:
        return {
            "content_hash": content_hash,
            "reused_analysis": False,
        }

    reporte = AnalysisReport.model_validate(
        registro.report_data
    )

    return {
        "execution_id": str(registro.execution_id),
        "status": "success",
        "content_hash": content_hash,
        "reused_analysis": True,
        "reused_analysis_at": registro.created_at,
        "report": reporte,
    }



@observe_agent("knowledge")
async def consultar_conocimiento(
    solicitud: ClauseAnalysisRequest,
    cliente: ClienteMCP,
) -> KnowledgeResponse:
    """Consulta evidencia jurídica para una cláusula mediante MCP."""

    consulta = build_legal_search_query(solicitud)

    contenido = await cliente.invocar(
        "conocimiento_juridico",
        {
            "query": consulta,
            "top_k": LEGAL_CONTEXT_RESULTS,
        },
    )

    try:
        respuesta = KnowledgeResponse.model_validate(contenido)
    except ValidationError as error:
        raise RuntimeError(
            "El Agente de Conocimiento Jurídico devolvió una respuesta inválida."
        ) from error

    if respuesta.status == "error":
        raise RuntimeError(respuesta.error or "No se pudo consultar la base jurídica.")

    return respuesta


@observe_agent("legal-analyzer")
async def analizar_clausula(
    solicitud: ClauseAnalysisRequest,
    conocimiento: KnowledgeResponse,
    cliente: ClienteMCP,
    trace_context: dict[str, str] | None = None,
    metricas_llm: list[LLMInvocationMetrics] | None = None,
) -> ClauseAnalysisResponse:
    """Analiza una cláusula con la evidencia recuperada mediante MCP."""

    argumentos = solicitud.model_dump(mode="json")
    argumentos["legal_context"] = [
        coincidencia.model_dump(mode="json") for coincidencia in conocimiento.matches
    ]

    active_trace_context = (
        get_current_trace_context()
        or trace_context
    )

    if active_trace_context is not None:
        argumentos["trace_context"] = active_trace_context

    contenido = await cliente.invocar(
        "analizador_legal",
        argumentos,
    )

    try:
        if "analysis" in contenido:
            tool_response = (
                LegalAnalyzerToolResponse.model_validate(
                    contenido
                )
            )
            respuesta = tool_response.analysis

            if (
                metricas_llm is not None
                and tool_response.observability is not None
            ):
                metricas_llm.append(
                    tool_response.observability
                )
        else:
            respuesta = (
                ClauseAnalysisResponse.model_validate(
                    contenido
                )
            )
    except ValidationError as error:
        raise RuntimeError(
            "El Agente Analizador Legal devolvió una respuesta inválida."
        ) from error

    if respuesta.status == "error":
        raise RuntimeError(respuesta.error or "No se pudo analizar la cláusula.")

    return respuesta


@observe_agent("observability")
async def consolidar_observabilidad(
    *,
    status: PipelineStatus,
    duration_ms: float,
    llm_metrics: list[LLMInvocationMetrics],
    error_count: int,
    cliente: ClienteMCP,
) -> ObservabilitySummary:
    """Consolida la telemetría mediante el Agente de Observabilidad MCP."""

    contenido = await cliente.invocar(
        "observabilidad",
        {
            "status": status,
            "duration_ms": duration_ms,
            "llm_metrics": [
                metrica.model_dump(mode="json")
                for metrica in llm_metrics
            ],
            "error_count": error_count,
        },
    )

    try:
        return ObservabilitySummary.model_validate(
            contenido
        )
    except ValidationError as error:
        raise RuntimeError(
            "El Agente de Observabilidad devolvió "
            "una respuesta inválida."
        ) from error


async def procesar_clausula(
    state: ClauseTaskState,
    cliente: ClienteMCP,
) -> ActualizacionEstado:
    """Coordina conocimiento y análisis para una cláusula independiente."""

    solicitud = state["analysis_request"]
    orden = solicitud.clause.order
    trace_context = state.get("trace_context")

    errores_conocimiento: list[dict[str, object]] = []
    intentos_conocimiento: dict[str, int] = {}

    try:
        conocimiento = await ejecutar_con_reintentos(
            partial(
                consultar_conocimiento,
                solicitud,
                cliente,
            )
        )
    except RuntimeError as error:
        conocimiento = KnowledgeResponse(
            status="success",
            query=build_legal_search_query(solicitud),
            matches=[],
        )
        errores_conocimiento = [
            {
                "step": "knowledge",
                "clause_order": orden,
                "message": str(error),
                "attempt": MAX_INTENTOS,
                "retryable": False,
            }
        ]
        intentos_conocimiento = {
            f"knowledge:{orden}": MAX_INTENTOS,
        }

    metricas_llm: list[LLMInvocationMetrics] = []

    try:
        respuesta = await ejecutar_con_reintentos(
            partial(
                analizar_clausula,
                solicitud,
                conocimiento,
                cliente,
                trace_context,
                metricas_llm,
            )
        )
    except RuntimeError as error:
        actualizacion_error = crear_actualizacion_error_clausula(
            "legal_analysis",
            orden,
            error,
        )

        if metricas_llm:
            actualizacion_error["llm_metrics"] = metricas_llm

        return actualizacion_error

    actualizacion: ActualizacionEstado = {
        "clause_results": {
            orden: respuesta,
        },
    }

    if metricas_llm:
        actualizacion["llm_metrics"] = metricas_llm

    if errores_conocimiento:
        actualizacion["errors"] = errores_conocimiento
        actualizacion["attempts"] = intentos_conocimiento

    return actualizacion


def decidir_continuacion(
    state: OrchestrationState,
) -> DecisionRuta:
    """Continúa el flujo si no existe un error global."""

    if state["status"] == "error":
        return "finalizar"

    return "continuar"


def distribuir_clausulas(
    state: OrchestrationState,
) -> DistribucionClausulas:
    """Crea una tarea independiente de LangGraph por cláusula."""

    if state["status"] == "error":
        return "finalizar"

    if state["reused_analysis"]:
        return "finalizar"

    contrato = state["preprocessed_contract"]

    if contrato is None or not contrato.clauses:
        return "finalizar"

    trace_context = get_current_trace_context()

    return [
        Send(
            "procesar_clausula",
            {
                "analysis_request": ClauseAnalysisRequest(
                    source_url=contrato.source_url,
                    platform=contrato.platform,
                    language=contrato.language,
                    clause=clausula,
                ),
                "trace_context": trace_context,
            },
        )
        for clausula in contrato.clauses
    ]


@observe_agent("report-generator")
async def generar_informe(
    state: OrchestrationState,
    cliente: ClienteMCP,
) -> ActualizacionEstado:
    """Ejecuta el Agente Generador de Informes mediante MCP."""

    contrato = state["preprocessed_contract"]

    if contrato is None:
        raise RuntimeError(
            "No existe un contrato preprocesado para generar el informe."
        )

    clausulas = [
        ClauseReportItem(
            clause_order=orden,
            analysis=respuesta,
        )
        for orden, respuesta in sorted(
            state["clause_results"].items()
        )
    ]

    solicitud = ReportGenerationRequest(
        execution_id=state["execution_id"],
        source_url=contrato.source_url,
        platform=contrato.platform,
        title=contrato.title,
        language=contrato.language,
        total_clauses=len(contrato.clauses),
        clauses=clausulas,
    )

    contenido = await cliente.invocar(
        "generador_informes",
        {
            "request": solicitud.model_dump(
                mode="json"
            )
        },
    )

    try:
        respuesta = ReportGenerationResponse.model_validate(
            contenido
        )
    except ValidationError as error:
        raise RuntimeError(
            "El Agente Generador de Informes devolvió "
            "una respuesta inválida."
        ) from error

    if respuesta.status == "error" or respuesta.report is None:
        raise RuntimeError(
            respuesta.error
            or "No se pudo generar el informe."
        )

    return {
        "current_step": "report_generation",
        "report": respuesta.report,
    }


def finalizar_flujo(
    state: OrchestrationState,
) -> ActualizacionEstado:
    """Calcula el estado final de la ejecución."""

    respuestas = tuple(state["clause_results"].values())
    exitosas = sum(respuesta.status == "success" for respuesta in respuestas)

    estado: PipelineStatus

    if state["status"] == "error":
        estado = "error"
    elif state["reused_analysis"] and state["report"] is not None or exitosas == len(respuestas) and respuestas:
        estado = "success"
    elif exitosas > 0:
        estado = "partial"
    else:
        estado = "error"

    contrato = state["preprocessed_contract"]
    clausulas_procesadas = len(contrato.clauses) if contrato is not None else 0

    return {
        "status": estado,
        "current_step": "finalization",
        "current_clause_index": clausulas_procesadas,
    }


def crear_orquestador(
    cliente: ClienteMCP,
) -> AgenteOrquestador:
    """Crea el orquestador conectado a los MCP."""

    nodos = NodosOrquestacion(
        extraer=partial(
            extraer_contrato,
            cliente=cliente,
        ),
        preprocesar=partial(
            preprocesar_contrato,
            cliente=cliente,
        ),
        verificar_analisis_previo=verificar_analisis_previo,
        procesar_clausula=partial(
            procesar_clausula,
            cliente=cliente,
        ),
        generar_informe=partial(
            generar_informe,
            cliente=cliente,
        ),
        finalizar=finalizar_flujo,
    )

    return AgenteOrquestador(
        nodos=nodos,
        distribuidor=distribuir_clausulas,
    )


async def ejecutar_orquestacion_async(
    request: ExtractionRequest,
) -> OrchestrationState:
    """Ejecuta el grafo usando conexiones MCP."""

    started_at = perf_counter()
    estado = create_initial_state(request)

    async with ClienteMCP() as cliente:
        grafo = crear_orquestador(cliente).construir()

        with start_pipeline_observation(
            estado["execution_id"]
        ) as observation:
            estado_final = await grafo.ainvoke(
                estado,
                config={
                    "max_concurrency": MAX_CLAUSULAS_CONCURRENTES,
                },
            )

            duration_ms = (
                perf_counter() - started_at
            ) * 1000

            try:
                estado_final["observability_summary"] = (
                    await consolidar_observabilidad(
                        status=estado_final["status"],
                        duration_ms=duration_ms,
                        llm_metrics=estado_final["llm_metrics"],
                        error_count=len(
                            estado_final["errors"]
                        ),
                        cliente=cliente,
                    )
                )
            except RuntimeError:
                estado_final["observability_summary"] = (
                    build_observability_summary(
                        status=estado_final["status"],
                        duration_ms=duration_ms,
                        llm_metrics=estado_final["llm_metrics"],
                        error_count=len(
                            estado_final["errors"]
                        ),
                    )
                )

            update_pipeline_observation(
                observation,
                status=estado_final["status"],
                reused_analysis=estado_final[
                    "reused_analysis"
                ],
                error_count=len(
                    estado_final["errors"]
                ),
            )

    observability_summary = estado_final[
        "observability_summary"
    ]

    if (
        observability_summary is not None
        and not estado_final["reused_analysis"]
    ):
        try:
            save_observability_run(
                execution_id=estado_final["execution_id"],
                summary=observability_summary,
            )
        except Exception:
            logger.exception(
                "No se pudo persistir la observabilidad "
                "de la ejecución %s.",
                estado_final["execution_id"],
            )

    reporte = estado_final["report"]
    content_hash = estado_final["content_hash"]
    status = estado_final["status"]

    if (
        not estado_final["reused_analysis"]
        and status in {"success", "partial"}
        and reporte is not None
        and content_hash is not None
    ):
        save_analysis(
            execution_id=estado_final["execution_id"],
            source_url=str(reporte.source_url),
            content_hash=content_hash,
            status=status,
            report=reporte,
            errors=estado_final["errors"],
            attempts=estado_final["attempts"],
        )

    return estado_final


def ejecutar_orquestacion(
    request: ExtractionRequest,
) -> OrchestrationState:
    """Conserva la entrada sincrona usada por la API."""

    return asyncio.run(
        ejecutar_orquestacion_async(request)
    )
