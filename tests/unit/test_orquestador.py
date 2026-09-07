from collections.abc import Callable

from app.agents.orquestador import (
    AgenteOrquestador,
    NodosOrquestacion,
)
from app.schemas.contract import ExtractionRequest
from app.schemas.orquestacion import (
    OrchestrationState,
    PipelineStatus,
    PipelineStep,
    create_initial_state,
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


def crear_orquestador(
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
            "knowledge",
            ejecutados,
        ),
        consultar_conocimiento=crear_nodo(
            "consultar_conocimiento",
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


def test_orquestador_compila_todos_los_nodos():
    orquestador = crear_orquestador([])
    grafo = orquestador.construir()

    nodos_esperados = {
        "extraer",
        "preprocesar",
        "consultar_conocimiento",
        "analizar_clausula",
        "registrar_resultado",
        "finalizar",
    }

    assert nodos_esperados.issubset(grafo.nodes)


def test_orquestador_ejecuta_el_flujo_definido():
    ejecutados: list[str] = []
    orquestador = crear_orquestador(ejecutados)
    grafo = orquestador.construir()

    resultado = grafo.invoke(crear_estado())

    assert ejecutados == [
        "extraer",
        "preprocesar",
        "consultar_conocimiento",
        "analizar_clausula",
        "registrar_resultado",
        "finalizar",
    ]
    assert resultado["status"] == "success"
    assert resultado["current_step"] == "finalization"
