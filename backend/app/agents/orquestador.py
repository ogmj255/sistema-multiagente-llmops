from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, TypeAlias

from langgraph.graph import END, START, StateGraph

from app.schemas.orquestacion import OrchestrationState

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


@dataclass(frozen=True)
class NodosOrquestacion:
    """Funciones que ejecutará el grafo de orquestación."""

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
        """Construye y compila el grafo de orquestación."""

        grafo = StateGraph(OrchestrationState)

        grafo.add_node("extraer", self._nodos.extraer)
        grafo.add_node(
            "preprocesar",
            self._nodos.preprocesar,
        )
        grafo.add_node(
            "consultar_conocimiento",
            self._nodos.consultar_conocimiento,
        )
        grafo.add_node(
            "analizar_clausula",
            self._nodos.analizar_clausula,
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
        grafo.add_edge("extraer", "preprocesar")
        grafo.add_edge(
            "preprocesar",
            "consultar_conocimiento",
        )
        grafo.add_edge(
            "consultar_conocimiento",
            "analizar_clausula",
        )
        grafo.add_edge(
            "analizar_clausula",
            "registrar_resultado",
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
