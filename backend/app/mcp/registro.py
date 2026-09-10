import sys
from contextlib import AsyncExitStack
from dataclasses import dataclass
from os import environ
from pathlib import Path
from types import TracebackType
from typing import Self

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult, TextContent

RUTA_BACKEND = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class ServidorMCP:
    """Configuración de un servidor y su herramienta principal."""

    nombre: str
    modulo: str
    herramienta: str
    variables_entorno: tuple[str, ...] = ()

    def crear_parametros(self) -> StdioServerParameters:
        """Crea los parámetros para iniciar el servidor por stdio."""
        entorno = {
            variable: environ[variable]
            for variable in self.variables_entorno
            if variable in environ
        }
        return StdioServerParameters(
            command=sys.executable,
            args=["-m", self.modulo],
            cwd=RUTA_BACKEND,
            env=entorno or None,
            encoding="utf-8",
            encoding_error_handler="strict",
        )


SERVIDORES_MCP: dict[str, ServidorMCP] = {
    "extractor_web": ServidorMCP(
        nombre="Agente Web Scraper",
        modulo="app.mcp.tools",
        herramienta="extract_saas_terms",
    ),
    "preprocesador": ServidorMCP(
        nombre="Agente Preprocesador",
        modulo="app.mcp.preprocessor_tools",
        herramienta="preprocess_saas_terms",
    ),
    "conocimiento_juridico": ServidorMCP(
        nombre="Agente de Conocimiento Jurídico",
        modulo="app.mcp.knowledge_tools",
        herramienta="search_legal_knowledge",
        variables_entorno=(
            "OLLAMA_BASE_URL",
            "OLLAMA_EMBEDDING_MODEL",
            "OLLAMA_EMBEDDING_DIMENSIONS",
            "LLM_TIMEOUT_SECONDS",
            "CHROMA_HOST",
            "CHROMA_PORT",
            "CHROMA_COLLECTION",
        ),
    ),
    "analizador_legal": ServidorMCP(
        nombre="Agente Analizador Legal",
        modulo="app.mcp.legal_analyzer_tools",
        herramienta="analyze_legal_clause",
        variables_entorno=(
            "LEGAL_ANALYZER_MODE",
            "LLM_TIMEOUT_SECONDS",
            "LLM_TEMPERATURE",
            "OLLAMA_BASE_URL",
            "OLLAMA_MODEL",
            "OLLAMA_CONTEXT_LENGTH",
            "OPENROUTER_BASE_URL",
            "OPENROUTER_API_KEY",
            "OPENROUTER_MODEL",
            "OPENROUTER_APP_NAME",
            "OPENROUTER_SITE_URL",
        ),
    ),
}


def obtener_servidor(clave: str) -> ServidorMCP:
    """Obtiene un servidor registrado mediante su clave."""

    try:
        return SERVIDORES_MCP[clave]
    except KeyError as error:
        raise KeyError(f"Servidor MCP no registrado: {clave}") from error


def listar_servidores() -> tuple[ServidorMCP, ...]:
    """Devuelve una vista inmutable del registro."""

    return tuple(SERVIDORES_MCP.values())


class ErrorInvocacionMCP(RuntimeError):
    """Indica que una herramienta MCP no pudo ejecutarse."""


def _obtener_detalle_error(
    resultado: CallToolResult,
) -> str:
    """Extrae el mensaje textual de un error MCP."""

    mensajes = [
        bloque.text for bloque in resultado.content if isinstance(bloque, TextContent)
    ]

    return " ".join(mensajes) or "La herramienta MCP devolvió un error."


class ClienteMCP:
    """Administra las conexiones con los servidores MCP."""

    def __init__(self) -> None:
        self._recursos = AsyncExitStack()
        self._sesiones: dict[str, ClientSession] = {}

    async def __aenter__(self) -> Self:
        for clave in SERVIDORES_MCP:
            await self._obtener_sesion(clave)

        return self

    async def __aexit__(
        self,
        _tipo_error: type[BaseException] | None,
        _error: BaseException | None,
        _traza: TracebackType | None,
    ) -> None:
        await self._recursos.aclose()

    async def _obtener_sesion(
        self,
        clave: str,
    ) -> ClientSession:
        if clave in self._sesiones:
            return self._sesiones[clave]

        servidor = obtener_servidor(clave)

        transporte = await self._recursos.enter_async_context(
            stdio_client(servidor.crear_parametros())
        )
        lector, escritor = transporte

        sesion = await self._recursos.enter_async_context(
            ClientSession(lector, escritor)
        )
        await sesion.initialize()

        self._sesiones[clave] = sesion
        return sesion

    async def invocar(
        self,
        clave: str,
        argumentos: dict[str, object],
    ) -> dict[str, object]:
        servidor = obtener_servidor(clave)

        try:
            sesion = await self._obtener_sesion(clave)
            resultado = await sesion.call_tool(
                servidor.herramienta,
                argumentos,
            )
        except Exception as error:
            raise ErrorInvocacionMCP(
                f"No se pudo invocar {servidor.nombre}: {error}"
            ) from error

        if resultado.isError:
            raise ErrorInvocacionMCP(_obtener_detalle_error(resultado))

        contenido = resultado.structuredContent

        if not isinstance(contenido, dict):
            raise ErrorInvocacionMCP(
                "La herramienta MCP no devolvió una respuesta estructurada."
            )

        return contenido
