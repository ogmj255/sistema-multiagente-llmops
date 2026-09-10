import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import partial
from typing import Literal, TypeAlias

from langgraph.errors import NodeError
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, RetryPolicy
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
    OrchestrationState,
    PipelineStatus,
    PipelineStep,
    create_initial_state,
)
from app.schemas.preprocessing import PreprocessingResponse

ActualizacionEstado: TypeAlias = dict[str, object]

NodoOrquestacion: TypeAlias = Callable[
    [OrchestrationState],
    ActualizacionEstado | Awaitable[ActualizacionEstado],
]

DecisionRuta = Literal[
    "continuar",
    "finalizar",
]

EnrutadorOrquestacion: TypeAlias = Callable[
    [OrchestrationState],
    DecisionRuta,
]

MAX_INTENTOS = 2
LIMITE_RECURSION = 1000

POLITICA_REINTENTOS = RetryPolicy(
    max_attempts=MAX_INTENTOS,
    jitter=False,
    retry_on=RuntimeError,
)

ETAPA_POR_NODO: dict[str, PipelineStep] = {
    "extraer": "extraction",
    "preprocesar": "preprocessing",
    "consultar_conocimiento": "knowledge",
    "analizar_clausula": "legal_analysis",
}


def manejar_error_nodo(
    state: OrchestrationState,
    error: NodeError,
) -> Command[Literal["registrar_resultado", "finalizar"]]:
    """Registra un error despues de agotar los intentos."""

    if not isinstance(error.error, RuntimeError):
        raise error.error

    etapa = ETAPA_POR_NODO[error.node]
    orden_clausula = None

    if etapa in {"knowledge", "legal_analysis"}:
        contrato = state["preprocessed_contract"]
        indice = state["current_clause_index"]

        if contrato is not None and indice < len(contrato.clauses):
            orden_clausula = contrato.clauses[indice].order

    clave_intento = etapa

    if orden_clausula is not None:
        clave_intento = f"{etapa}:{orden_clausula}"

    errores = list(state["errors"])
    errores.append(
        {
            "step": etapa,
            "clause_order": orden_clausula,
            "message": str(error.error),
            "attempt": MAX_INTENTOS,
            "retryable": True,
        }
    )

    intentos = dict(state["attempts"])
    intentos[clave_intento] = MAX_INTENTOS

    if etapa in {"knowledge", "legal_analysis"} and orden_clausula is not None:
        resultados = dict(state["clause_results"])
        resultados[orden_clausula] = ClauseAnalysisResponse(
            status="error",
            error=str(error.error),
        )

        return Command(
            update={
                "status": "running",
                "current_step": "record_result",
                "clause_results": resultados,
                "errors": errores,
                "attempts": intentos,
            },
            goto="registrar_resultado",
        )

    return Command(
        update={
            "status": "error",
            "current_step": etapa,
            "errors": errores,
            "attempts": intentos,
        },
        goto="finalizar",
    )


@dataclass(frozen=True)
class NodosOrquestacion:
    """Funciones que ejecutará el grafo."""

    extraer: NodoOrquestacion
    preprocesar: NodoOrquestacion
    consultar_conocimiento: NodoOrquestacion
    analizar_clausula: NodoOrquestacion
    registrar_resultado: NodoOrquestacion
    finalizar: NodoOrquestacion


class AgenteOrquestador:
    """Construye el flujo multiagente mediante LangGraph."""

    def __init__(
        self,
        nodos: NodosOrquestacion,
        enrutador: EnrutadorOrquestacion,
    ) -> None:
        self._nodos = nodos
        self._enrutador = enrutador

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
            "consultar_conocimiento",
            self._nodos.consultar_conocimiento,
            retry_policy=POLITICA_REINTENTOS,
            error_handler=manejar_error_nodo,
        )
        grafo.add_node(
            "analizar_clausula",
            self._nodos.analizar_clausula,
            retry_policy=POLITICA_REINTENTOS,
            error_handler=manejar_error_nodo,
        )
        grafo.add_node(
            "registrar_resultado",
            self._nodos.registrar_resultado,
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
            decidir_continuacion,
            {
                "continuar": "consultar_conocimiento",
                "finalizar": "finalizar",
            },
        )

        grafo.add_conditional_edges(
            "consultar_conocimiento",
            decidir_continuacion,
            {
                "continuar": "analizar_clausula",
                "finalizar": "finalizar",
            },
        )

        grafo.add_conditional_edges(
            "analizar_clausula",
            decidir_continuacion,
            {
                "continuar": "registrar_resultado",
                "finalizar": "finalizar",
            },
        )

        grafo.add_conditional_edges(
            "registrar_resultado",
            self._enrutador,
            {
                "continuar": "consultar_conocimiento",
                "finalizar": "finalizar",
            },
        )

        grafo.add_edge("finalizar", END)

        return grafo.compile()


def crear_solicitud_analisis(
    state: OrchestrationState,
) -> ClauseAnalysisRequest:
    """Crea la solicitud para la cláusula actual."""

    contrato = state["preprocessed_contract"]

    if contrato is None:
        raise RuntimeError("No existe un contrato preprocesado.")

    indice = state["current_clause_index"]

    if indice >= len(contrato.clauses):
        raise RuntimeError("El índice de cláusula está fuera del contrato.")

    return ClauseAnalysisRequest(
        source_url=contrato.source_url,
        platform=contrato.platform,
        language=contrato.language,
        jurisdiction=state["jurisdiction"],
        clause=contrato.clauses[indice],
    )


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
    state: OrchestrationState,
    cliente: ClienteMCP,
) -> ActualizacionEstado:
    """Consulta evidencia jurídica mediante MCP."""

    solicitud = crear_solicitud_analisis(state)
    consulta = build_legal_search_query(solicitud)

    contenido = await cliente.invocar(
        "conocimiento_juridico",
        {
            "query": consulta,
            "top_k": LEGAL_CONTEXT_RESULTS,
            "jurisdiction": state["jurisdiction"],
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

    return {
        "current_step": "legal_analysis",
        "knowledge_response": respuesta,
    }


async def analizar_clausula(
    state: OrchestrationState,
    cliente: ClienteMCP,
) -> ActualizacionEstado:
    """Ejecuta el Analizador Legal mediante MCP."""

    solicitud = crear_solicitud_analisis(state)
    conocimiento = state["knowledge_response"]

    if conocimiento is None or not conocimiento.matches:
        raise RuntimeError("No existe evidencia jurídica para analizar la cláusula.")

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

    resultados = dict(state["clause_results"])
    resultados[solicitud.clause.order] = respuesta

    return {
        "current_step": "record_result",
        "clause_results": resultados,
    }


def registrar_resultado(
    state: OrchestrationState,
) -> ActualizacionEstado:
    """Avanza a la siguiente cláusula del contrato."""

    contrato = state["preprocessed_contract"]
    siguiente_indice = state["current_clause_index"] + 1

    if contrato is not None and siguiente_indice < len(contrato.clauses):
        siguiente_paso = "knowledge"
    else:
        siguiente_paso = "finalization"

    return {
        "current_clause_index": siguiente_indice,
        "current_step": siguiente_paso,
        "knowledge_response": None,
    }


def decidir_continuacion(
    state: OrchestrationState,
) -> DecisionRuta:
    """Continua el flujo si no existe un error."""

    if state["status"] == "error":
        return "finalizar"

    return "continuar"


def decidir_siguiente(
    state: OrchestrationState,
) -> DecisionRuta:
    """Decide si quedan cláusulas por analizar."""

    contrato = state["preprocessed_contract"]

    if contrato is not None and state["current_clause_index"] < len(contrato.clauses):
        return "continuar"

    return "finalizar"


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

    return {
        "status": estado,
        "current_step": "finalization",
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
        consultar_conocimiento=partial(
            consultar_conocimiento,
            cliente=cliente,
        ),
        analizar_clausula=partial(
            analizar_clausula,
            cliente=cliente,
        ),
        registrar_resultado=registrar_resultado,
        finalizar=finalizar_flujo,
    )

    return AgenteOrquestador(
        nodos=nodos,
        enrutador=decidir_siguiente,
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
                "recursion_limit": LIMITE_RECURSION,
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
