import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import partial
from typing import Literal, TypeAlias, TypeVar

from langgraph.errors import NodeError
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, RetryPolicy, Send
from pydantic import ValidationError

from app.agents.legal_analyzer_agent import (
    LEGAL_CONTEXT_RESULTS,
    build_legal_search_query,
)
from app.mcp.registro import ClienteMCP
from app.schemas.contract import (
    ExtractionRequest,
    ExtractionResponse,
)
from app.schemas.knowledge import KnowledgeResponse
from app.schemas.legal_analysis import (
    ClauseAnalysisRequest,
    ClauseAnalysisResponse,
)
from app.schemas.legal_corpus import Jurisdiction
from app.schemas.orquestacion import (
    ClauseTaskState,
    OrchestrationState,
    PipelineStatus,
    PipelineStep,
    create_initial_state,
)
from app.schemas.preprocessing import PreprocessingResponse

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
MAX_CLAUSULAS_CONCURRENTES = 5

POLITICA_REINTENTOS = RetryPolicy(
    max_attempts=MAX_INTENTOS,
    jitter=False,
    retry_on=RuntimeError,
)

ETAPA_POR_NODO: dict[str, PipelineStep] = {
    "extraer": "extraction",
    "preprocesar": "preprocessing",
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
                    "retryable": True,
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
    procesar_clausula: NodoClausula
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
            "procesar_clausula",
            self._nodos.procesar_clausula,
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

        grafo.add_conditional_edges(
            "preprocesar",
            self._distribuidor,
            [
                "procesar_clausula",
                "finalizar",
            ],
        )

        grafo.add_edge(
            "procesar_clausula",
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
                "retryable": True,
            }
        ],
        "attempts": {
            f"{etapa}:{orden_clausula}": MAX_INTENTOS,
        },
    }


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

    if not respuesta.matches:
        raise RuntimeError(
            "El Agente de Conocimiento Jurídico no recuperó evidencia para la cláusula."
        )

    return respuesta


async def analizar_clausula(
    solicitud: ClauseAnalysisRequest,
    conocimiento: KnowledgeResponse,
    cliente: ClienteMCP,
) -> ClauseAnalysisResponse:
    """Analiza una cláusula con la evidencia recuperada mediante MCP."""

    argumentos = solicitud.model_dump(mode="json")
    argumentos["legal_context"] = [
        coincidencia.model_dump(mode="json") for coincidencia in conocimiento.matches
    ]

    contenido = await cliente.invocar(
        "analizador_legal",
        argumentos,
    )

    try:
        respuesta = ClauseAnalysisResponse.model_validate(contenido)
    except ValidationError as error:
        raise RuntimeError(
            "El Agente Analizador Legal devolvió una respuesta inválida."
        ) from error

    if respuesta.status == "error":
        raise RuntimeError(respuesta.error or "No se pudo analizar la cláusula.")

    return respuesta


async def procesar_clausula(
    state: ClauseTaskState,
    cliente: ClienteMCP,
) -> ActualizacionEstado:
    """Coordina conocimiento y análisis para una cláusula independiente."""

    solicitud = state["analysis_request"]
    orden = solicitud.clause.order

    try:
        conocimiento = await ejecutar_con_reintentos(
            partial(
                consultar_conocimiento,
                solicitud,
                cliente,
            )
        )
    except RuntimeError as error:
        return crear_actualizacion_error_clausula(
            "knowledge",
            orden,
            error,
        )

    try:
        respuesta = await ejecutar_con_reintentos(
            partial(
                analizar_clausula,
                solicitud,
                conocimiento,
                cliente,
            )
        )
    except RuntimeError as error:
        return crear_actualizacion_error_clausula(
            "legal_analysis",
            orden,
            error,
        )

    return {
        "clause_results": {
            orden: respuesta,
        },
    }


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

    contrato = state["preprocessed_contract"]

    if contrato is None or not contrato.clauses:
        return "finalizar"

    return [
        Send(
            "procesar_clausula",
            {
                "analysis_request": ClauseAnalysisRequest(
                    source_url=contrato.source_url,
                    platform=contrato.platform,
                    language=contrato.language,
                    jurisdiction=state["jurisdiction"],
                    clause=clausula,
                )
            },
        )
        for clausula in contrato.clauses
    ]


def finalizar_flujo(
    state: OrchestrationState,
) -> ActualizacionEstado:
    """Calcula el estado final de la ejecución."""

    respuestas = tuple(state["clause_results"].values())
    exitosas = sum(respuesta.status == "success" for respuesta in respuestas)

    estado: PipelineStatus

    if exitosas == len(respuestas) and respuestas:
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
        procesar_clausula=partial(
            procesar_clausula,
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
    jurisdiction: Jurisdiction = "ecuador",
) -> OrchestrationState:
    """Ejecuta el grafo usando conexiones MCP."""

    estado = create_initial_state(
        request,
        jurisdiction,
    )

    async with ClienteMCP() as cliente:
        grafo = crear_orquestador(cliente).construir()

        return await grafo.ainvoke(
            estado,
            config={
                "max_concurrency": MAX_CLAUSULAS_CONCURRENTES,
            },
        )


def ejecutar_orquestacion(
    request: ExtractionRequest,
    jurisdiction: Jurisdiction = "ecuador",
) -> OrchestrationState:
    """Conserva la entrada síncrona usada por la API."""

    return asyncio.run(
        ejecutar_orquestacion_async(
            request,
            jurisdiction,
        )
    )
