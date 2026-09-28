import asyncio
import inspect
import re
from collections.abc import Awaitable, Callable
from contextlib import nullcontext
from datetime import UTC, datetime
from types import SimpleNamespace, TracebackType
from typing import Self, TypeAlias
from uuid import uuid4

import pytest
from app.agents import orchestrator_agent
from app.agents.orchestrator_agent import (
    AgenteOrquestador,
    NodosOrquestacion,
)
from app.core import observability as core_observability
from app.schemas.contract import (
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
from app.schemas.orchestration import (
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
from app.schemas.report import (
    AnalysisReport,
    ClassificationSummary,
    ReportGenerationRequest,
    ReportGenerationResponse,
)
from langgraph.types import Send

RespuestaMCP: TypeAlias = dict[str, object] | Awaitable[dict[str, object]]

RespondedorMCP: TypeAlias = Callable[
    [str, dict[str, object]],
    RespuestaMCP,
]


class ClienteMCPFalso:
    """Simula los servidores MCP del orchestrator_agent."""

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

    def responder_con_observabilidad(
        clave: str,
        argumentos: dict[str, object],
    ) -> RespuestaMCP:
        if clave == "observabilidad":
            metricas = [
                orchestrator_agent.LLMInvocationMetrics.model_validate(
                    metrica
                )
                for metrica in argumentos["llm_metrics"]
            ]

            return orchestrator_agent.build_observability_summary(
                status=argumentos["status"],
                duration_ms=argumentos["duration_ms"],
                llm_metrics=metricas,
                error_count=argumentos["error_count"],
            ).model_dump(mode="json")

        return responder(
            clave,
            argumentos,
        )

    cliente = ClienteMCPFalso(
        responder_con_observabilidad
    )

    def crear_cliente() -> ClienteMCPFalso:
        return cliente

    monkeypatch.setattr(
        orchestrator_agent,
        "ClienteMCP",
        crear_cliente,
    )


@pytest.fixture(autouse=True)
def aislar_persistencia(
    monkeypatch,
) -> None:
    """Evita que los tests unitarios dependan de PostgreSQL real."""

    monkeypatch.setattr(
        orchestrator_agent,
        "find_successful_analysis",
        lambda _source_url, _content_hash: None,
    )
    monkeypatch.setattr(
        orchestrator_agent,
        "save_analysis",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        orchestrator_agent,
        "save_observability_run",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        orchestrator_agent,
        "start_pipeline_observation",
        lambda _execution_id: nullcontext(None),
    )
    monkeypatch.setattr(
        orchestrator_agent,
        "update_pipeline_observation",
        lambda _observation, **_kwargs: None,
    )
    monkeypatch.setattr(
        orchestrator_agent,
        "get_current_trace_context",
        lambda: None,
    )
    monkeypatch.setattr(
        core_observability,
        "get_observability_client",
        lambda: None,
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
        verificar_analisis_previo=crear_nodo(
            "verificar_analisis_previo",
            "knowledge",
            ejecutados,
        ),
        procesar_clausula=crear_nodo(
            "procesar_clausula",
            "legal_analysis",
            ejecutados,
        ),
        generar_informe=crear_nodo(
            "generar_informe",
            "report_generation",
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
        retrieved_at=datetime.now(UTC),
        extraction_method="httpx",
        raw_html="""
        <html lang="es">
            <body>
                <main>
                    <h1>Terms</h1>
                    <p>Contenido contractual.</p>
                </main>
            </body>
        </html>
        """,
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
        category="Condiciones contractuales",
        clause_type="Disposición contractual",
        target="Usuario",
        consequence=None,
        classification="not_potentially_abusive",
        analysis_status="classified",
        relevant_fragment=f"Contenido contractual {orden}.",
        justification=(
            "No se identificaron indicios de abusividad."
        ),
        recommendation="Mantener la redacción.",
        evidence_sufficiency="sufficient",
        legal_basis=[crear_evidencia()],
    )

    return ClauseAnalysisResponse(
        status="success",
        result=valoracion,
    )


def crear_respuesta_informe(
    argumentos: dict[str, object],
) -> ReportGenerationResponse:
    datos = argumentos["request"]

    assert isinstance(datos, dict)

    solicitud = ReportGenerationRequest.model_validate(
        datos
    )

    exitosas = sum(
        item.analysis.status == "success"
        for item in solicitud.clauses
    )
    fallidas = len(solicitud.clauses) - exitosas

    return ReportGenerationResponse(
        status="success",
        report=AnalysisReport(
            execution_id=solicitud.execution_id,
            source_url=solicitud.source_url,
            platform=solicitud.platform,
            title=solicitud.title,
            language=solicitud.language,
            total_clauses=solicitud.total_clauses,
            analyzed_clauses=len(solicitud.clauses),
            successful_clauses=exitosas,
            failed_clauses=fallidas,
            classification_summary=ClassificationSummary(
                not_potentially_abusive=exitosas,
            ),
            clauses=solicitud.clauses,
        ),
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
        "verificar_analisis_previo",
        "procesar_clausula",
        "generar_informe",
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
        "verificar_analisis_previo",
        "procesar_clausula",
        "generar_informe",
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

        if clave == "generador_informes":
            return crear_respuesta_informe(
                argumentos
            ).model_dump(mode="json")

        raise AssertionError(f"Servidor MCP inesperado: {clave}")

    usar_cliente_mcp_falso(monkeypatch, responder)

    resultado = orchestrator_agent.ejecutar_orquestacion(
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

        if clave == "generador_informes":
            return crear_respuesta_informe(
                argumentos
            ).model_dump(mode="json")

        raise AssertionError(f"Servidor MCP inesperado: {clave}")

    usar_cliente_mcp_falso(monkeypatch, responder)

    resultado = orchestrator_agent.ejecutar_orquestacion(
        ExtractionRequest(
            url="https://example.com/terms",
            platform="Example",
        )
    )

    assert orchestrator_agent.MAX_CLAUSULAS_CONCURRENTES == 1
    assert maximo_activas == 1
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

    resultado = orchestrator_agent.ejecutar_orquestacion(
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
            "retryable": False,
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

        if clave == "generador_informes":
            return crear_respuesta_informe(
                argumentos
            ).model_dump(mode="json")

        raise AssertionError(f"Servidor MCP inesperado: {clave}")

    usar_cliente_mcp_falso(monkeypatch, responder)

    resultado = orchestrator_agent.ejecutar_orquestacion(
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

            return crear_respuesta_conocimiento(
                str(argumentos["query"])
            ).model_dump(mode="json")

        if clave == "analizador_legal":
            orden = obtener_orden_analisis(argumentos)
            llamadas.append(f"analizador_legal:{orden}")

            if orden == 1:
                assert argumentos["legal_context"] == []
            else:
                assert argumentos["legal_context"] == [
                    crear_evidencia().model_dump(mode="json")
                ]

            return crear_respuesta_legal(
                orden
            ).model_dump(mode="json")

        if clave == "generador_informes":
            return crear_respuesta_informe(
                argumentos
            ).model_dump(mode="json")

        raise AssertionError(
            f"Servidor MCP inesperado: {clave}"
        )

    usar_cliente_mcp_falso(monkeypatch, responder)

    resultado = orchestrator_agent.ejecutar_orquestacion(
        ExtractionRequest(
            url="https://example.com/terms",
            platform="Example",
        )
    )

    assert llamadas.count("conocimiento_juridico:1") == 2
    assert llamadas.count("analizador_legal:1") == 1
    assert llamadas.count("conocimiento_juridico:2") == 1
    assert llamadas.count("analizador_legal:2") == 1

    assert resultado["current_clause_index"] == 2
    assert resultado["status"] == "success"
    assert resultado["clause_results"][1].status == "success"
    assert resultado["clause_results"][2].status == "success"

    assert resultado["attempts"] == {
        "knowledge:1": 2,
    }
    assert resultado["errors"][0]["step"] == "knowledge"
    assert resultado["errors"][0]["clause_order"] == 1


def test_finalizacion_conserva_error_global():
    estado = crear_estado()
    estado["status"] = "error"
    estado["preprocessed_contract"] = crear_contrato_preprocesado()
    estado["clause_results"] = {
        1: crear_respuesta_legal(1),
        2: crear_respuesta_legal(2),
    }

    resultado = orchestrator_agent.finalizar_flujo(estado)

    assert resultado["status"] == "error"


def test_reutiliza_analisis_previo_sin_repetir_agentes(
    monkeypatch,
):
    execution_id = uuid4()

    reporte_previo = AnalysisReport(
        execution_id=str(execution_id),
        source_url="https://example.com/terms",
        platform="Example",
        title="Terms",
        language="es",
        total_clauses=2,
        analyzed_clauses=2,
        successful_clauses=2,
        failed_clauses=0,
        classification_summary=ClassificationSummary(
            not_potentially_abusive=2,
        ),
        clauses=[],
    )

    created_at = datetime.now(UTC)

    registro = SimpleNamespace(
        execution_id=execution_id,
        report_data=reporte_previo.model_dump(
            mode="json"
        ),
        created_at=created_at,
    )

    monkeypatch.setattr(
        orchestrator_agent,
        "find_successful_analysis",
        lambda _source_url, _content_hash: registro,
    )

    def no_guardar(**_kwargs) -> None:
        raise AssertionError(
            "Un análisis reutilizado no debe guardarse nuevamente."
        )

    monkeypatch.setattr(
        orchestrator_agent,
        "save_analysis",
        no_guardar,
    )

    llamadas: list[str] = []

    def responder(
        clave: str,
        _: dict[str, object],
    ) -> dict[str, object]:
        llamadas.append(clave)

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

        raise AssertionError(
            f"No debía ejecutarse el servidor MCP: {clave}"
        )

    usar_cliente_mcp_falso(
        monkeypatch,
        responder,
    )

    observabilidad_guardada: list[
        dict[str, object]
    ] = []

    monkeypatch.setattr(
        orchestrator_agent,
        "save_observability_run",
        lambda **kwargs: observabilidad_guardada.append(
            kwargs
        ),
    )

    resultado = orchestrator_agent.ejecutar_orquestacion(
        ExtractionRequest(
            url="https://example.com/terms",
            platform="Example",
        )
    )

    assert llamadas == [
        "extractor_web",
        "preprocesador",
    ]
    assert resultado["execution_id"] == str(execution_id)
    assert resultado["status"] == "success"
    assert resultado["reused_analysis"] is True
    assert observabilidad_guardada == []
    assert resultado["reused_analysis_at"] == created_at
    assert resultado["report"] == reporte_previo
    assert resultado["clause_results"] == {}


def test_persiste_analisis_nuevo_exitoso(
    monkeypatch,
):
    guardados: list[dict[str, object]] = []

    monkeypatch.setattr(
        orchestrator_agent,
        "find_successful_analysis",
        lambda _source_url, _content_hash: None,
    )

    def guardar(**kwargs) -> None:
        guardados.append(kwargs)

    monkeypatch.setattr(
        orchestrator_agent,
        "save_analysis",
        guardar,
    )

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
            return crear_respuesta_conocimiento(
                str(argumentos["query"])
            ).model_dump(mode="json")

        if clave == "analizador_legal":
            orden = obtener_orden_analisis(argumentos)
            return crear_respuesta_legal(
                orden
            ).model_dump(mode="json")

        if clave == "generador_informes":
            return crear_respuesta_informe(
                argumentos
            ).model_dump(mode="json")

        raise AssertionError(
            f"Servidor MCP inesperado: {clave}"
        )

    usar_cliente_mcp_falso(
        monkeypatch,
        responder,
    )

    resultado = orchestrator_agent.ejecutar_orquestacion(
        ExtractionRequest(
            url="https://example.com/terms",
            platform="Example",
        )
    )

    assert resultado["status"] == "success"
    assert resultado["reused_analysis"] is False
    assert len(guardados) == 1

    guardado = guardados[0]

    assert guardado["execution_id"] == resultado["execution_id"]
    assert guardado["source_url"] == "https://example.com/terms"
    assert guardado["status"] == "success"
    assert guardado["report"] == resultado["report"]
    assert guardado["errors"] == []
    assert guardado["content_hash"] == (
        orchestrator_agent.calculate_content_hash(
            crear_contrato_preprocesado().cleaned_text
        )
    )


def test_persiste_analisis_parcial(
    monkeypatch,
):
    guardados: list[dict[str, object]] = []

    def guardar(**kwargs) -> None:
        guardados.append(kwargs)

    monkeypatch.setattr(
        orchestrator_agent,
        "save_analysis",
        guardar,
    )

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
            return crear_respuesta_conocimiento(
                str(argumentos["query"])
            ).model_dump(mode="json")

        if clave == "analizador_legal":
            orden = obtener_orden_analisis(argumentos)

            if orden == 1:
                return ClauseAnalysisResponse(
                    status="error",
                    error="Error temporal de análisis.",
                ).model_dump(mode="json")

            return crear_respuesta_legal(
                orden
            ).model_dump(mode="json")

        if clave == "generador_informes":
            return crear_respuesta_informe(
                argumentos
            ).model_dump(mode="json")

        raise AssertionError(
            f"Servidor MCP inesperado: {clave}"
        )

    usar_cliente_mcp_falso(
        monkeypatch,
        responder,
    )

    resultado = orchestrator_agent.ejecutar_orquestacion(
        ExtractionRequest(
            url="https://example.com/terms",
            platform="Example",
        )
    )

    assert resultado["status"] == "partial"
    assert resultado["reused_analysis"] is False
    assert len(guardados) == 1

    guardado = guardados[0]

    assert guardado["status"] == "partial"
    assert guardado["execution_id"] == resultado["execution_id"]
    assert guardado["report"] == resultado["report"]
    assert guardado["errors"] == resultado["errors"]
    assert guardado["errors"][0]["clause_order"] == 1




def test_analizador_legal_prioriza_contexto_activo_del_agente(
    monkeypatch,
) -> None:
    """Propaga al MCP el contexto activo del agente legal."""

    contexto_raiz = {
        "trace_id": "a" * 32,
        "parent_span_id": "root-span",
    }
    contexto_agente = {
        "trace_id": "a" * 32,
        "parent_span_id": "legal-agent-span",
    }
    capturado: dict[str, object] = {}

    async def responder(
        clave: str,
        argumentos: dict[str, object],
    ) -> dict[str, object]:
        assert clave == "analizador_legal"
        capturado.update(argumentos)

        return crear_respuesta_legal(1).model_dump(
            mode="json"
        )

    cliente = ClienteMCPFalso(responder)

    monkeypatch.setattr(
        orchestrator_agent,
        "get_current_trace_context",
        lambda: contexto_agente,
    )

    analizar_sin_decorador = (
        orchestrator_agent.analizar_clausula.__wrapped__
    )

    respuesta = asyncio.run(
        analizar_sin_decorador(
            crear_solicitud_analisis(),
            crear_respuesta_conocimiento("consulta"),
            cliente,
            trace_context=contexto_raiz,
        )
    )

    assert respuesta.status == "success"
    assert capturado["trace_context"] == contexto_agente


def test_analizador_legal_conserva_metricas_del_envelope_mcp():
    async def responder(
        clave: str,
        argumentos: dict[str, object],
    ) -> dict[str, object]:
        assert clave == "analizador_legal"

        return {
            "analysis": crear_respuesta_legal(1).model_dump(
                mode="json"
            ),
            "observability": {
                "provider": "openrouter",
                "model": "model-test",
                "prompt_tokens": 120,
                "completion_tokens": 30,
                "total_tokens": 150,
                "cost_usd": 0.0042,
            },
        }

    cliente = ClienteMCPFalso(responder)
    metricas_llm = []

    analizar_sin_decorador = (
        orchestrator_agent.analizar_clausula.__wrapped__
    )

    respuesta = asyncio.run(
        analizar_sin_decorador(
            crear_solicitud_analisis(),
            crear_respuesta_conocimiento("consulta"),
            cliente,
            metricas_llm=metricas_llm,
        )
    )

    assert respuesta.status == "success"
    assert len(metricas_llm) == 1

    metrica = metricas_llm[0]

    assert metrica.provider == "openrouter"
    assert metrica.model == "model-test"
    assert metrica.prompt_tokens == 120
    assert metrica.completion_tokens == 30
    assert metrica.total_tokens == 150
    assert metrica.cost_usd == 0.0042


def test_consolida_observabilidad_mediante_mcp():
    capturado: dict[str, object] = {}

    async def responder(
        clave: str,
        argumentos: dict[str, object],
    ) -> dict[str, object]:
        assert clave == "observabilidad"
        capturado.update(argumentos)

        return {
            "status": "partial",
            "duration_ms": 1250.0,
            "prompt_tokens": 100,
            "completion_tokens": 25,
            "total_tokens": 125,
            "cost_usd": 0.0035,
            "error_count": 1,
            "llm_invocation_count": 1,
        }

    cliente = ClienteMCPFalso(responder)

    metricas = [
        orchestrator_agent.LLMInvocationMetrics(
            provider="openrouter",
            model="model-test",
            prompt_tokens=100,
            completion_tokens=25,
            total_tokens=125,
            cost_usd=0.0035,
        )
    ]

    consolidar_sin_decorador = (
        orchestrator_agent.consolidar_observabilidad.__wrapped__
    )

    resumen = asyncio.run(
        consolidar_sin_decorador(
            status="partial",
            duration_ms=1250.0,
            llm_metrics=metricas,
            error_count=1,
            cliente=cliente,
        )
    )

    assert capturado["status"] == "partial"
    assert capturado["duration_ms"] == 1250.0
    assert capturado["error_count"] == 1

    metricas_enviadas = capturado["llm_metrics"]
    assert isinstance(metricas_enviadas, list)
    assert len(metricas_enviadas) == 1
    assert metricas_enviadas[0]["total_tokens"] == 125
    assert metricas_enviadas[0]["cost_usd"] == 0.0035

    assert resumen.status == "partial"
    assert resumen.duration_ms == 1250.0
    assert resumen.total_tokens == 125
    assert resumen.cost_usd == 0.0035
    assert resumen.error_count == 1
    assert resumen.llm_invocation_count == 1
