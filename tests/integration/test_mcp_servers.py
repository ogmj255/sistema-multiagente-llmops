import pytest
from app.mcp.registro import (
    ServidorMCP,
    listar_servidores,
)
from mcp import ClientSession
from mcp.client.stdio import stdio_client


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "servidor",
    listar_servidores(),
    ids=lambda servidor: servidor.nombre,
)
async def test_servidor_expone_herramienta_registrada(
    servidor: ServidorMCP,
) -> None:
    """Inicia un servidor real y consulta sus herramientas por stdio."""

    async with stdio_client(servidor.crear_parametros()) as transporte:
        lector, escritor = transporte

        async with ClientSession(
            lector,
            escritor,
        ) as sesion:
            await sesion.initialize()
            resultado = await sesion.list_tools()

    herramientas = {herramienta.name for herramienta in resultado.tools}
    assert servidor.herramienta in herramientas
