import sys
from pathlib import Path

import pytest
from app.mcp.registro import (
    RUTA_BACKEND,
    SERVIDORES_MCP,
    listar_servidores,
    obtener_servidor,
)


def test_registra_los_cuatro_servidores():
    assert set(SERVIDORES_MCP) == {
        "extractor_web",
        "preprocesador",
        "conocimiento_juridico",
        "analizador_legal",
    }


def test_registra_modulos_y_herramientas_correctos():
    esperados = {
        "extractor_web": (
            "app.mcp.tools",
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
        assert (
            parametros.encoding_error_handler
            == "strict"
        )


def test_modulos_y_herramientas_no_se_duplican():
    servidores = listar_servidores()

    assert len({
        servidor.modulo
        for servidor in servidores
    }) == len(servidores)

    assert len({
        servidor.herramienta
        for servidor in servidores
    }) == len(servidores)


def test_rechaza_servidor_no_registrado():
    with pytest.raises(
        KeyError,
        match="Servidor MCP no registrado",
    ):
        obtener_servidor("desconocido")
