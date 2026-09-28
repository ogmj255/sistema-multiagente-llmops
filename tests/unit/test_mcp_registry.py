import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from mcp.types import TextContent

from app.mcp import registry as mcp_registry
from app.mcp.registry import (
    RUTA_BACKEND,
    SERVIDORES_MCP,
    ClienteMCP,
    ErrorInvocacionMCP,
    listar_servidores,
    obtener_servidor,
)


class SesionMCPFalsa:
    """Simula una sesión MCP sin iniciar servidores."""

    def __init__(
        self,
        resultado: SimpleNamespace,
    ) -> None:
        self.resultado = resultado
        self.llamadas: list[tuple[str, dict[str, object]]] = []

    async def call_tool(
        self,
        herramienta: str,
        argumentos: dict[str, object],
    ) -> SimpleNamespace:
        self.llamadas.append((herramienta, argumentos))
        return self.resultado


def preparar_cliente(
    monkeypatch,
    resultado: SimpleNamespace,
) -> tuple[ClienteMCP, SesionMCPFalsa]:
    """Configura un cliente con una sesión simulada."""

    cliente = ClienteMCP()
    sesion = SesionMCPFalsa(resultado)

    async def obtener_sesion(
        _: str,
    ) -> SesionMCPFalsa:
        return sesion

    monkeypatch.setattr(
        cliente,
        "_obtener_sesion",
        obtener_sesion,
    )

    return cliente, sesion


def test_registra_los_seis_servidores():
    assert set(SERVIDORES_MCP) == {
        "extractor_web",
        "preprocesador",
        "conocimiento_juridico",
        "analizador_legal",
        "generador_informes",
        "observabilidad",
    }


def test_registra_modulos_y_herramientas_correctos():
    esperados = {
        "extractor_web": (
            "app.mcp.web_scraper_tools",
            "extract_saas_terms",
        ),
        "preprocesador": (
            "app.mcp.preprocessor_tools",
            "preprocess_saas_terms",
        ),
        "conocimiento_juridico": (
            "app.mcp.knowledge_tools",
            "search_legal_knowledge",
        ),
        "analizador_legal": (
            "app.mcp.legal_analyzer_tools",
            "analyze_legal_clause",
        ),
        "generador_informes": (
            "app.mcp.report_generator_tools",
            "generate_analysis_report",
        ),
    }

    for clave, esperado in esperados.items():
        servidor = obtener_servidor(clave)

        assert (
            servidor.modulo,
            servidor.herramienta,
        ) == esperado


def test_crea_parametros_stdio_reproducibles():
    for servidor in listar_servidores():
        parametros = servidor.crear_parametros()

        assert parametros.command == sys.executable
        assert parametros.args == [
            "-m",
            servidor.modulo,
        ]
        assert Path(parametros.cwd) == RUTA_BACKEND
        assert parametros.encoding == "utf-8"
        assert parametros.encoding_error_handler == "strict"


def test_modulos_y_herramientas_no_se_duplican():
    servidores = listar_servidores()

    assert len({servidor.modulo for servidor in servidores}) == len(servidores)

    assert len({servidor.herramienta for servidor in servidores}) == len(servidores)


def test_rechaza_servidor_no_registrado():
    with pytest.raises(
        KeyError,
        match="Servidor MCP no registrado",
    ):
        obtener_servidor("desconocido")


def test_cliente_invoca_herramienta_registrada(
    monkeypatch,
):
    argumentos = {
        "url": "https://example.com/terms",
    }
    resultado = SimpleNamespace(
        isError=False,
        structuredContent={
            "status": "success",
        },
        content=[],
    )
    cliente, sesion = preparar_cliente(
        monkeypatch,
        resultado,
    )

    respuesta = asyncio.run(
        cliente.invocar(
            "extractor_web",
            argumentos,
        )
    )

    assert respuesta == {
        "status": "success",
    }
    assert sesion.llamadas == [
        (
            "extract_saas_terms",
            argumentos,
        )
    ]


def test_cliente_registra_error_de_herramienta(
    monkeypatch,
):
    resultado = SimpleNamespace(
        isError=True,
        structuredContent=None,
        content=[
            TextContent(
                type="text",
                text="Error MCP de prueba.",
            )
        ],
    )
    cliente, _ = preparar_cliente(
        monkeypatch,
        resultado,
    )

    with pytest.raises(
        ErrorInvocacionMCP,
        match="Error MCP de prueba",
    ):
        asyncio.run(
            cliente.invocar(
                "extractor_web",
                {},
            )
        )


def test_cliente_rechaza_respuesta_no_estructurada(
    monkeypatch,
):
    resultado = SimpleNamespace(
        isError=False,
        structuredContent=None,
        content=[],
    )
    cliente, _ = preparar_cliente(
        monkeypatch,
        resultado,
    )

    with pytest.raises(
        ErrorInvocacionMCP,
        match="respuesta estructurada",
    ):
        asyncio.run(
            cliente.invocar(
                "extractor_web",
                {},
            )
        )


def test_cliente_prepara_sesiones_antes_del_grafo(
    monkeypatch,
):
    cliente = ClienteMCP()
    servidores_abiertos: list[str] = []

    async def obtener_sesion(
        clave: str,
    ) -> SimpleNamespace:
        servidores_abiertos.append(clave)
        return SimpleNamespace()

    monkeypatch.setattr(
        cliente,
        "_obtener_sesion",
        obtener_sesion,
    )

    async def ejecutar() -> None:
        async with cliente:
            pass

    asyncio.run(ejecutar())

    assert servidores_abiertos == list(SERVIDORES_MCP)


def test_transmite_entorno_segun_servidor(
    monkeypatch,
):
    monkeypatch.setenv(
        "OLLAMA_BASE_URL",
        "http://ollama-prueba:11434",
    )
    monkeypatch.setenv(
        "CHROMA_HOST",
        "chroma-prueba",
    )
    monkeypatch.setenv(
        "OPENROUTER_API_KEY",
        "clave-prueba",
    )
    monkeypatch.setenv(
        "POSTGRES_PASSWORD",
        "no-debe-transmitirse",
    )

    conocimiento = obtener_servidor("conocimiento_juridico").crear_parametros()
    analizador = obtener_servidor("analizador_legal").crear_parametros()
    extractor = obtener_servidor("extractor_web").crear_parametros()
    preprocesador = obtener_servidor("preprocesador").crear_parametros()

    assert conocimiento.env is not None
    assert conocimiento.env["OLLAMA_BASE_URL"] == ("http://ollama-prueba:11434")
    assert conocimiento.env["CHROMA_HOST"] == ("chroma-prueba")
    assert "OPENROUTER_API_KEY" not in conocimiento.env
    assert "POSTGRES_PASSWORD" not in conocimiento.env

    assert analizador.env is not None
    assert "OLLAMA_BASE_URL" not in analizador.env
    assert analizador.env["OPENROUTER_API_KEY"] == ("clave-prueba")
    assert "CHROMA_HOST" not in analizador.env
    assert "POSTGRES_PASSWORD" not in analizador.env

    assert extractor.env is None

    assert preprocesador.env is not None
    assert preprocesador.env["OLLAMA_BASE_URL"] == (
        "http://ollama-prueba:11434"
    )
    assert "CHROMA_HOST" not in preprocesador.env
    assert "OPENROUTER_API_KEY" not in preprocesador.env
    assert "POSTGRES_PASSWORD" not in preprocesador.env



def test_cliente_registra_invocacion_mcp_exitosa(
    monkeypatch,
) -> None:
    """Registra como exitosa una herramienta MCP ejecutada."""

    resultado = SimpleNamespace(
        isError=False,
        structuredContent={
            "status": "success",
        },
        content=[],
    )
    cliente, _ = preparar_cliente(
        monkeypatch,
        resultado,
    )

    observation = object()
    started: dict[str, object] = {}
    updated: dict[str, object] = {}

    class FakeContext:
        def __enter__(self) -> object:
            return observation

        def __exit__(
            self,
            exc_type,
            exc_value,
            traceback,
        ) -> None:
            return None

    def fake_start(
        server: str,
        tool: str,
    ) -> FakeContext:
        started.update(
            {
                "server": server,
                "tool": tool,
            }
        )
        return FakeContext()

    def fake_update(
        received_observation: object,
        *,
        status: str,
    ) -> None:
        updated.update(
            {
                "observation": received_observation,
                "status": status,
            }
        )

    monkeypatch.setattr(
        mcp_registry,
        "start_mcp_tool_observation",
        fake_start,
    )
    monkeypatch.setattr(
        mcp_registry,
        "update_operation_observation",
        fake_update,
    )

    respuesta = asyncio.run(
        cliente.invocar(
            "extractor_web",
            {
                "url": "https://example.com/terms",
            },
        )
    )

    servidor = obtener_servidor("extractor_web")

    assert respuesta == {
        "status": "success",
    }
    assert started == {
        "server": servidor.nombre,
        "tool": servidor.herramienta,
    }
    assert updated == {
        "observation": observation,
        "status": "success",
    }


def test_cliente_registra_error_mcp_real(
    monkeypatch,
) -> None:
    """Registra el error real devuelto por una herramienta MCP."""

    resultado = SimpleNamespace(
        isError=True,
        structuredContent=None,
        content=[
            TextContent(
                type="text",
                text="Error MCP observado.",
            )
        ],
    )
    cliente, _ = preparar_cliente(
        monkeypatch,
        resultado,
    )

    observation = object()
    captured: dict[str, object] = {}

    class FakeContext:
        def __enter__(self) -> object:
            return observation

        def __exit__(
            self,
            exc_type,
            exc_value,
            traceback,
        ) -> None:
            return None

    monkeypatch.setattr(
        mcp_registry,
        "start_mcp_tool_observation",
        lambda *_args: FakeContext(),
    )

    def fake_mark_error(
        received_observation: object,
        error: Exception,
    ) -> None:
        captured["observation"] = received_observation
        captured["error"] = error

    monkeypatch.setattr(
        mcp_registry,
        "mark_operation_error",
        fake_mark_error,
    )

    with pytest.raises(
        ErrorInvocacionMCP,
        match="Error MCP observado",
    ):
        asyncio.run(
            cliente.invocar(
                "extractor_web",
                {},
            )
        )

    assert captured["observation"] is observation
    assert isinstance(
        captured["error"],
        ErrorInvocacionMCP,
    )
    assert "Error MCP observado" in str(
        captured["error"]
    )
