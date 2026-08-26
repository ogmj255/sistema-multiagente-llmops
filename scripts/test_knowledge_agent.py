from app.agents.knowledge_agent import (
    run_knowledge_agent,
)
from app.schemas.knowledge import KnowledgeQuery


def main() -> None:
    """Prueba el agente contra la base jurídica real."""

    request = KnowledgeQuery(
        query=(
            "¿Qué obligaciones existen para proteger "
            "los datos personales?"
        ),
        top_k=3,
        jurisdiction="ecuador",
    )

    response = run_knowledge_agent(request)

    print("Estado:", response.status)
    print("Consulta:", response.query)
    print("Resultados:", len(response.matches))

    if response.error is not None:
        print("Error:", response.error)
        raise SystemExit(1)

    for index, match in enumerate(
        response.matches,
        start=1,
    ):
        print("\n" + "=" * 60)
        print("Resultado:", index)
        print("Documento:", match.title)
        print("ID:", match.document_id)
        print("Segmento:", match.chunk_id)
        print(
            "Distancia:",
            f"{match.distance:.6f}",
        )
        print("Fuente:", match.source_url)
        print(
            "Contenido:",
            match.content[:500],
        )


if __name__ == "__main__":
    main()