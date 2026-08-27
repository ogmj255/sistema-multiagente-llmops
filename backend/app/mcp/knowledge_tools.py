from asyncio import to_thread

from mcp.server.fastmcp import FastMCP

from app.agents.knowledge_agent import (
    run_knowledge_agent,
)
from app.schemas.knowledge import KnowledgeQuery
from app.schemas.legal_corpus import (
    Jurisdiction,
    LegalDocumentType,
)

mcp = FastMCP("Agente de Conocimiento Jurídico")


@mcp.tool()
async def search_legal_knowledge(
    query: str,
    top_k: int = 5,
    jurisdiction: Jurisdiction | None = None,
    document_type: LegalDocumentType | None = None,
) -> dict[str, object]:
    """Recupera normativa relevante desde la base jurídica."""

    request = KnowledgeQuery(
        query=query,
        top_k=top_k,
        jurisdiction=jurisdiction,
        document_type=document_type,
    )

    response = await to_thread(
        run_knowledge_agent,
        request,
    )

    return response.model_dump(mode="json")


if __name__ == "__main__":
    mcp.run()