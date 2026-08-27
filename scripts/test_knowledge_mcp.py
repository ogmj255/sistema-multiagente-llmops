import asyncio
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> None:
    """Prueba el servidor MCP jurídico mediante stdio."""

    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(
        Path.cwd() / "backend"
    )

    parameters = StdioServerParameters(
        command=sys.executable,
        args=[
            "-m",
            "app.mcp.knowledge_tools",
        ],
        env=environment,
    )

    async with stdio_client(parameters) as streams:
        read_stream, write_stream = streams

        async with ClientSession(
            read_stream,
            write_stream,
        ) as session:
            await session.initialize()

            available_tools = await session.list_tools()
            tool_names = [
                tool.name
                for tool in available_tools.tools
            ]

            print("Herramientas:", tool_names)

            assert (
                "search_legal_knowledge"
                in tool_names
            )

            result = await session.call_tool(
                "search_legal_knowledge",
                arguments={
                    "query": (
                        "¿Qué obligaciones existen para "
                        "proteger los datos personales?"
                    ),
                    "top_k": 3,
                    "jurisdiction": "ecuador",
                },
            )

            print("Error MCP:", result.isError)

            for content in result.content:
                text = getattr(content, "text", None)

                if text is not None:
                    print(text)

            if result.isError:
                raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())