import sys
from dataclasses import dataclass
from pathlib import Path

from mcp import StdioServerParameters

RUTA_BACKEND = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class ServidorMCP:
    """Configuración de un servidor y su herramienta principal."""

    nombre: str
    modulo: str
    herramienta: str

    def crear_parametros(self) -> StdioServerParameters:
        """Crea los parámetros para iniciar el servidor por stdio."""

        return StdioServerParameters(
            command=sys.executable,
            args=["-m", self.modulo],
            cwd=RUTA_BACKEND,
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
    ),
    "analizador_legal": ServidorMCP(
        nombre="Agente Analizador Legal",
        modulo="app.mcp.legal_analyzer_tools",
        herramienta="analyze_legal_clause",
    ),
}


def obtener_servidor(clave: str) -> ServidorMCP:
    """Obtiene un servidor registrado mediante su clave."""

    try:
        return SERVIDORES_MCP[clave]
    except KeyError as error:
        raise KeyError(
            f"Servidor MCP no registrado: {clave}"
        ) from error


def listar_servidores() -> tuple[ServidorMCP, ...]:
    """Devuelve una vista inmutable del registro."""

    return tuple(SERVIDORES_MCP.values())
