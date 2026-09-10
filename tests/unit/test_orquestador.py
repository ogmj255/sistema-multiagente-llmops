import asyncio
import inspect
import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from types import TracebackType
from typing import Self, TypeAlias

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
from app.schemas.knowledge import (
    KnowledgeResponse,
    LegalKnowledgeMatch,
)
from app.schemas.legal_analysis import (
    ClauseAnalysisRequest,
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
from langgraph.types import Send

RespuestaMCP: TypeAlias = dict[str, object] | Awaitable[dict[str, object]]

RespondedorMCP: TypeAlias = Callable[
    [str, dict[str, object]],
    RespuestaMCP,
]


class ClienteMCPFalso:
    """Simula los servidores MCP del orquestador."""

    def __init__(
        self,
        responder: RespondedorMCP,
    ) -> None:
        self._responder = responder

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        _tipo_error: type[BaseException] | None,
        _error: BaseException | None,
        _traza: TracebackType | None,
    ) -> None:
        return None

    async def invocar(
        self,
        clave: str,
        argumentos: dict[str, object],
    ) -> dict[str, object]:
        respuesta = self._responder(
            clave,
            argumentos,
        )

        if inspect.isawaitable(respuesta):
            return await respuesta

        return respuesta


def usar_cliente_mcp_falso(
    monkeypatch,
    responder: RespondedorMCP,
) -> None:
    """Reemplaza el cliente real sin iniciar procesos."""

    cliente = ClienteMCPFalso(responder)

    def crear_cliente() -> ClienteMCPFalso:
        return cliente

    monkeypatch.setattr(
        orquestador,
        "ClienteMCP",
        crear_cliente,
    )


def crear_nodo(
    nombre: str,
    etapa: PipelineStep,
    ejecutados: list[str],
    estado: PipelineStatus = "running",
) -> Callable[[object], dict[str, object]]:
    def ejecutar(
        _: object,
    ) -> dict[str, object]:
        ejecutados.append(nombre)

        return {
            "status": estado,
            "current_step": etapa,
        }

    return ejecutar


def crear_solicitud_analisis(
    orden: int = 1,
) -> ClauseAnalysisRequest:
    return ClauseAnalysisRequest(
        source_url="https://example.com/terms",
        platform="Example",
        language="es",
        jurisdiction="ecuador",
        clause=ProcessedClause(
            order=orden,
            original_order=orden,
            heading=f"Cláusula {orden}",
            heading_level=2,
            content=f"Contenido contractual {orden}.",
        ),
    )


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
            "knowledge",
            ejecutados,
        ),
        procesar_clausula=crear_nodo(
            "procesar_clausula",
            "legal_analysis",
            ejecutados,
        ),
        finalizar=crear_nodo(
            "finalizar",
            "finalization",
            ejecutados,
            estado="success",
        ),
    )

    def distribuir(
        _: OrchestrationState,
    ) -> list[Send]:
        return [
            Send(
                "procesar_clausula",
                {
                    "analysis_request": crear_solicitud_analisis(),
                },
            )
        ]

    return AgenteOrquestador(
        nodos=nodos,
        distribuidor=distribuir,
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


def crear_contrato_preprocesado(
    cantidad: int = 2,
) -> PreprocessedContract:
    clausulas = [
        crear_solicitud_analisis(orden).clause for orden in range(1, cantidad + 1)
    ]

    return PreprocessedContract(
        source_url="https://example.com/terms",
        platform="Example",
        title="Terms",
        language="es",
        cleaned_text=" ".join(clausula.content for clausula in clausulas),
        clauses=clausulas,
        removed_blocks=[],
    )


def crear_evidencia() -> LegalKnowledgeMatch:
    return LegalKnowledgeMatch(
        chunk_id="ec_ley_consumidor_chunk_0001",
        document_id="ec_ley_consumidor",
        chunk_index=1,
        content="Normativa aplicable a relaciones de consumo.",
        title="Ley de Defensa del Consumidor",
        jurisdiction="ecuador",
        issuing_body="Congreso Nacional del Ecuador",
        document_type="law",
        binding_level="binding",
        status="in_force",
        language="es",
        source_url="https://example.com/ley",
        official_citation="Registro Oficial",
        topics="consumidores|contratos",
        checksum="a" * 64,
        distance=0.1,
    )


def crear_respuesta_conocimiento(
    consulta: str,
) -> KnowledgeResponse:
    return KnowledgeResponse(
        status="success",
        query=consulta,
        matches=[crear_evidencia()],
    )


def crear_respuesta_legal(
    orden: int,
) -> ClauseAnalysisResponse:
    valoracion = ClauseAssessment(
        category="other_contractual_risk",
        classification="fair",
        analysis_status="classified",
        relevant_fragment=f"Contenido contractual {orden}.",
        justification="No se identificó un riesgo.",
        recommendation="Mantener la redacción.",
        evidence_sufficiency="sufficient",
        legal_basis=[crear_evidencia()],
    )

    return ClauseAnalysisResponse(
        status="success",
        result=valoracion,
    )


def obtener_orden_consulta(
    argumentos: dict[str, object],
) -> int:
    consulta = str(argumentos["query"])
    coincidencia = re.search(
        r"Cláusula: Contenido contractual (\d+)\.",
        consulta,
    )

    if coincidencia is None:
        raise AssertionError("La consulta no contiene la cláusula esperada.")

    return int(coincidencia.group(1))


def obtener_orden_analisis(
    argumentos: dict[str, object],
) -> int:
    clausula = argumentos["clause"]

    assert isinstance(clausula, dict)
    orden = clausula["order"]
    assert isinstance(orden, int)

    return orden


def test_orquestador_compila_todos_los_nodos():
    grafo = crear_orquestador_controlado([]).construir()

    nodos_esperados = {
        "extraer",
        "preprocesar",
        "procesar_clausula",
        "finalizar",
    }

    assert nodos_esperados.issubset(grafo.nodes)


def test_orquestador_ejecuta_el_flujo_definido():
    ejecutados: list[str] = []

    grafo = crear_orquestador_controlado(ejecutados).construir()
    resultado = grafo.invoke(crear_estado())

    assert ejecutados == [
        "extraer",
        "preprocesar",
        "procesar_clausula",
        "finalizar",
    ]
    assert resultado["status"] == "success"


def test_coordina_cada_clausula_mediante_mcp(
    monkeypatch,
):
    llamadas: list[str] = []

    def responder(
        clave: str,
        argumentos: dict[str, object],
    ) -> dict[str, object]:
        if clave == "extractor_web":
            llamadas.append("extractor_web")

            if llamadas.count("extractor_web") == 1:
                return ExtractionResponse(
                    status="error",
                    error="Error temporal de extracción.",
                ).model_dump(mode="json")

            return ExtractionResponse(
                status="success",
                contract=crear_contrato_extraido(),
            ).model_dump(mode="json")

        if clave == "preprocesador":
            llamadas.append("preprocesador")

            return PreprocessingResponse(
                status="success",
                result=crear_contrato_preprocesado(),
            ).model_dump(mode="json")

        if clave == "conocimiento_juridico":
            orden = obtener_orden_consulta(argumentos)
            llamadas.append(f"conocimiento_juridico:{orden}")
            assert "jurisdiction" not in argumentos
            return crear_respuesta_conocimiento(str(argumentos["query"])).model_dump(
                mode="json"
            )

        if clave == "analizador_legal":
            orden = obtener_orden_analisis(argumentos)
            llamadas.append(f"analizador_legal:{orden}")

            assert argumentos["legal_context"] == [
                crear_evidencia().model_dump(mode="json")
            ]

            return crear_respuesta_legal(orden).model_dump(mode="json")

        raise AssertionError(f"Servidor MCP inesperado: {clave}")

    usar_cliente_mcp_falso(monkeypatch, responder)

    resultado = orquestador.ejecutar_orquestacion(
        ExtractionRequest(
            url="https://example.com/terms",
            platform="Example",
        )
    )

    assert llamadas.count("extractor_web") == 2
    assert llamadas.count("preprocesador") == 1

    for orden in (1, 2):
        consulta = f"conocimiento_juridico:{orden}"
        analisis = f"analizador_legal:{orden}"

        assert llamadas.count(consulta) == 1
        assert llamadas.count(analisis) == 1
        assert llamadas.index(consulta) < llamadas.index(analisis)

    assert resultado["current_clause_index"] == 2
    assert set(resultado["clause_results"]) == {
        1,
        2,
    }
    assert resultado["status"] == "success"


def test_limita_concurrencia_a_cinco_clausulas(
    monkeypatch,
):
    activas = 0
    maximo_activas = 0

    async def responder(
        clave: str,
        argumentos: dict[str, object],
    ) -> dict[str, object]:
        nonlocal activas, maximo_activas

        if clave == "extractor_web":
            return ExtractionResponse(
                status="success",
                contract=crear_contrato_extraido(),
            ).model_dump(mode="json")

        if clave == "preprocesador":
            return PreprocessingResponse(
                status="success",
                result=crear_contrato_preprocesado(8),
            ).model_dump(mode="json")

        activas += 1
        maximo_activas = max(
            maximo_activas,
            activas,
        )

        try:
            await asyncio.sleep(0.01)

            if clave == "conocimiento_juridico":
                return crear_respuesta_conocimiento(
                    str(argumentos["query"])
                ).model_dump(mode="json")

            if clave == "analizador_legal":
                orden = obtener_orden_analisis(argumentos)
                return crear_respuesta_legal(orden).model_dump(mode="json")
        finally:
            activas -= 1

        raise AssertionError(f"Servidor MCP inesperado: {clave}")

    usar_cliente_mcp_falso(monkeypatch, responder)

    resultado = orquestador.ejecutar_orquestacion(
        ExtractionRequest(
            url="https://example.com/terms",
            platform="Example",
        )
    )

    assert orquestador.MAX_CLAUSULAS_CONCURRENTES == 5
    assert maximo_activas == 5
    assert len(resultado["clause_results"]) == 8
    assert resultado["status"] == "success"


def test_registra_error_al_agotar_reintentos(
    monkeypatch,
):
    intentos = 0

    def responder(
        clave: str,
        _: dict[str, object],
    ) -> dict[str, object]:
        nonlocal intentos

        assert clave == "extractor_web"
        intentos += 1

        return ExtractionResponse(
            status="error",
            error="Servicio temporal no disponible.",
        ).model_dump(mode="json")

    usar_cliente_mcp_falso(monkeypatch, responder)

    resultado = orquestador.ejecutar_orquestacion(
        ExtractionRequest(
            url="https://example.com/terms",
            platform="Example",
        )
    )

    assert intentos == 2
    assert resultado["status"] == "error"
    assert resultado["attempts"] == {
        "extraction": 2,
    }
    assert resultado["errors"] == [
        {
            "step": "extraction",
            "clause_order": None,
            "message": "Servicio temporal no disponible.",
            "attempt": 2,
            "retryable": True,
        }
    ]


def test_continua_despues_de_error_en_clausula(
    monkeypatch,
):
    llamadas: list[str] = []

    def responder(
        clave: str,
        argumentos: dict[str, object],
    ) -> dict[str, object]:
        if clave == "extractor_web":
            return ExtractionResponse(
                status="success",
                contract=crear_contrato_extraido(),
            ).model_dump(mode="json")

        if clave == "preprocesador":
            return PreprocessingResponse(
                status="success",
                result=crear_contrato_preprocesado(),
            ).model_dump(mode="json")

        if clave == "conocimiento_juridico":
            orden = obtener_orden_consulta(argumentos)
            llamadas.append(f"conocimiento_juridico:{orden}")

            return crear_respuesta_conocimiento(str(argumentos["query"])).model_dump(
                mode="json"
            )

        if clave == "analizador_legal":
            orden = obtener_orden_analisis(argumentos)
            llamadas.append(f"analizador_legal:{orden}")

            if orden == 1:
                return ClauseAnalysisResponse(
                    status="error",
                    error="Error temporal de análisis.",
                ).model_dump(mode="json")

            return crear_respuesta_legal(orden).model_dump(mode="json")

        raise AssertionError(f"Servidor MCP inesperado: {clave}")

    usar_cliente_mcp_falso(monkeypatch, responder)

    resultado = orquestador.ejecutar_orquestacion(
        ExtractionRequest(
            url="https://example.com/terms",
            platform="Example",
        )
    )

    assert llamadas.count("conocimiento_juridico:1") == 1
    assert llamadas.count("analizador_legal:1") == 2
    assert llamadas.count("conocimiento_juridico:2") == 1
    assert llamadas.count("analizador_legal:2") == 1
    assert resultado["current_clause_index"] == 2
    assert resultado["status"] == "partial"
    assert resultado["clause_results"][1].status == "error"
    assert resultado["clause_results"][2].status == "success"
    assert resultado["attempts"] == {
        "legal_analysis:1": 2,
    }
    assert resultado["errors"][0]["clause_order"] == 1


def test_continua_despues_de_error_de_conocimiento(
    monkeypatch,
):
    llamadas: list[str] = []

    def responder(
        clave: str,
        argumentos: dict[str, object],
    ) -> dict[str, object]:
        if clave == "extractor_web":
            return ExtractionResponse(
                status="success",
                contract=crear_contrato_extraido(),
            ).model_dump(mode="json")

        if clave == "preprocesador":
            return PreprocessingResponse(
                status="success",
                result=crear_contrato_preprocesado(),
            ).model_dump(mode="json")

        if clave == "conocimiento_juridico":
            orden = obtener_orden_consulta(argumentos)
            llamadas.append(f"conocimiento_juridico:{orden}")

            if orden == 1:
                return KnowledgeResponse(
                    status="error",
                    query=str(argumentos["query"]),
                    error="Error temporal de conocimiento.",
                ).model_dump(mode="json")

            return crear_respuesta_conocimiento(str(argumentos["query"])).model_dump(
                mode="json"
            )

        if clave == "analizador_legal":
            orden = obtener_orden_analisis(argumentos)
            llamadas.append(f"analizador_legal:{orden}")

            return crear_respuesta_legal(orden).model_dump(mode="json")

        raise AssertionError(f"Servidor MCP inesperado: {clave}")

    usar_cliente_mcp_falso(monkeypatch, responder)

    resultado = orquestador.ejecutar_orquestacion(
        ExtractionRequest(
            url="https://example.com/terms",
            platform="Example",
        )
    )

    assert llamadas.count("conocimiento_juridico:1") == 2
    assert "analizador_legal:1" not in llamadas
    assert llamadas.count("conocimiento_juridico:2") == 1
    assert llamadas.count("analizador_legal:2") == 1
    assert resultado["current_clause_index"] == 2
    assert resultado["status"] == "partial"
    assert resultado["clause_results"][1].status == "error"
    assert resultado["clause_results"][2].status == "success"
    assert resultado["attempts"] == {
        "knowledge:1": 2,
    }
    assert resultado["errors"][0]["step"] == "knowledge"
