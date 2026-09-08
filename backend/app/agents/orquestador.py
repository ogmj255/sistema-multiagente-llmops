from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, TypeAlias

from langgraph.errors import NodeError
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy

from app.agents.legal_analyzer_agent import (
    run_legal_analyzer_agent,
)
from app.agents.preprocessor_agent import (
    run_preprocessor_agent,
)
from app.agents.web_scraper_agent import (
    run_web_scraper_agent,
)
from app.schemas.contract import ExtractionRequest
from app.schemas.legal_analysis import ClauseAnalysisRequest
from app.schemas.legal_corpus import Jurisdiction
from app.schemas.orquestacion import (
    OrchestrationState,
    PipelineStatus,
    PipelineStep,
    create_initial_state,
)

ActualizacionEstado: TypeAlias = dict[str, object]

NodoOrquestacion: TypeAlias = Callable[
    [OrchestrationState],
    ActualizacionEstado,
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

POLITICA_REINTENTOS = RetryPolicy(
    max_attempts=MAX_INTENTOS,
    jitter=False,
    retry_on=RuntimeError,
)

ETAPA_POR_NODO: dict[str, PipelineStep] = {
    "extraer": "extraction",
    "preprocesar": "preprocessing",
    "analizar_clausula": "legal_analysis",
}


def manejar_error_nodo(
    state: OrchestrationState,
    error: NodeError,
) -> ActualizacionEstado:
    """Registra un error despues de agotar los intentos."""

    if not isinstance(error.error, RuntimeError):
        raise error.error

    etapa = ETAPA_POR_NODO[error.node]
    orden_clausula = None

    if etapa == "legal_analysis":
        contrato = state["preprocessed_contract"]
        indice = state["current_clause_index"]

        if (
            contrato is not None
            and indice < len(contrato.clauses)
        ):
            orden_clausula = (
                contrato.clauses[indice].order
            )

    clave_intento = etapa

    if orden_clausula is not None:
        clave_intento = (
            f"{etapa}:{orden_clausula}"
        )

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

    return {
        "status": "error",
        "current_step": etapa,
        "errors": errores,
        "attempts": intentos,
    }


@dataclass(frozen=True)
class NodosOrquestacion:
    """Funciones que ejecutará el grafo."""

    extraer: NodoOrquestacion
    preprocesar: NodoOrquestacion
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
                "continuar": "analizar_clausula",
                "finalizar": "finalizar",
            },
        )

        grafo.add_edge("finalizar", END)

        return grafo.compile()


def extraer_contrato(
    state: OrchestrationState,
) -> ActualizacionEstado:
    """Ejecuta el Agente Web Scraper."""

    respuesta = run_web_scraper_agent(
        state["request"]
    )

    if (
        respuesta.status == "error"
        or respuesta.contract is None
    ):
        raise RuntimeError(
            respuesta.error
            or "No se pudo extraer el contrato."
        )

    return {
        "status": "running",
        "current_step": "preprocessing",
        "extracted_contract": respuesta.contract,
    }


def preprocesar_contrato(
    state: OrchestrationState,
) -> ActualizacionEstado:
    """Ejecuta el Agente Preprocesador."""

    contrato = state["extracted_contract"]

    if contrato is None:
        raise RuntimeError(
            "No existe un contrato para preprocesar."
        )

    respuesta = run_preprocessor_agent(contrato)

    if (
        respuesta.status == "error"
        or respuesta.result is None
    ):
        raise RuntimeError(
            respuesta.error
            or "No se pudo preprocesar el contrato."
        )

    return {
        "current_step": "legal_analysis",
        "preprocessed_contract": respuesta.result,
    }


def analizar_clausula(
    state: OrchestrationState,
) -> ActualizacionEstado:
    """Ejecuta el Analizador Legal para la cláusula actual."""

    contrato = state["preprocessed_contract"]

    if contrato is None:
        raise RuntimeError(
            "No existe un contrato preprocesado."
        )

    indice = state["current_clause_index"]

    if indice >= len(contrato.clauses):
        raise RuntimeError(
            "El índice de cláusula está fuera del contrato."
        )

    clausula = contrato.clauses[indice]

    solicitud = ClauseAnalysisRequest(
        source_url=contrato.source_url,
        platform=contrato.platform,
        language=contrato.language,
        jurisdiction=state["jurisdiction"],
        clause=clausula,
    )

    respuesta = run_legal_analyzer_agent(solicitud)

    if respuesta.status == "error":
        raise RuntimeError(
            respuesta.error
            or "No se pudo analizar la clausula."
        )

    resultados = dict(state["clause_results"])
    resultados[clausula.order] = respuesta

    return {
        "current_step": "record_result",
        "clause_results": resultados,
    }


def registrar_resultado(
    state: OrchestrationState,
) -> ActualizacionEstado:
    """Avanza a la siguiente cl?usula del contrato."""

    contrato = state["preprocessed_contract"]
    siguiente_indice = (
        state["current_clause_index"] + 1
    )

    if (
        contrato is not None
        and siguiente_indice < len(contrato.clauses)
    ):
        siguiente_paso = "legal_analysis"
    else:
        siguiente_paso = "finalization"

    return {
        "current_clause_index": siguiente_indice,
        "current_step": siguiente_paso,
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

    if (
        contrato is not None
        and state["current_clause_index"]
        < len(contrato.clauses)
    ):
        return "continuar"

    return "finalizar"


def finalizar_flujo(
    state: OrchestrationState,
) -> ActualizacionEstado:
    """Calcula el estado final de la ejecución."""

    respuestas = tuple(
        state["clause_results"].values()
    )

    exitosas = sum(
        respuesta.status == "success"
        for respuesta in respuestas
    )

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


def crear_orquestador() -> AgenteOrquestador:
    """Crea el orquestador con los agentes existentes."""

    nodos = NodosOrquestacion(
        extraer=extraer_contrato,
        preprocesar=preprocesar_contrato,
        analizar_clausula=analizar_clausula,
        registrar_resultado=registrar_resultado,
        finalizar=finalizar_flujo,
    )

    return AgenteOrquestador(
        nodos=nodos,
        enrutador=decidir_siguiente,
    )


def ejecutar_orquestacion(
    request: ExtractionRequest,
    jurisdiction: Jurisdiction = "ecuador",
) -> OrchestrationState:
    """Ejecuta el análisis secuencial completo."""

    estado = create_initial_state(
        request,
        jurisdiction,
    )

    grafo = crear_orquestador().construir()

    return grafo.invoke(estado)
