from fastapi import APIRouter
from fastapi.encoders import jsonable_encoder

from app.agents.orquestador import ejecutar_orquestacion
from app.schemas.contract import ExtractionRequest
from app.schemas.legal_corpus import Jurisdiction

router = APIRouter()


@router.get("/", tags=["General"])
def root() -> dict[str, str]:
    """Muestra informacion general de la API."""
    return {
        "message": "Sistema Multiagente LLMOps",
        "version": "0.1.0",
    }


@router.get("/health", tags=["Health"])
def health() -> dict[str, str]:
    """Comprueba que el servicio esta funcionando."""
    return {
        "status": "ok",
        "service": "backend",
    }


@router.post("/analisis", tags=["Analisis"])
def analizar_terminos(
    request: ExtractionRequest,
    jurisdiction: Jurisdiction = "ecuador",
) -> dict[str, object]:
    """Ejecuta el pipeline desde una URL de terminos."""

    estado = ejecutar_orquestacion(
        request,
        jurisdiction,
    )

    respuestas = estado["clause_results"]

    resultados = [
        {
            "clause_order": orden,
            **jsonable_encoder(respuesta),
        }
        for orden, respuesta in sorted(
            respuestas.items()
        )
    ]

    exitosas = sum(
        respuesta.status == "success"
        for respuesta in respuestas.values()
    )
    contrato = estado["preprocessed_contract"]

    return jsonable_encoder(
        {
            "execution_id": estado["execution_id"],
            "status": estado["status"],
            "source_url": request.url,
            "platform": (
                contrato.platform
                if contrato is not None
                else request.platform
            ),
            "jurisdiction": estado["jurisdiction"],
            "total_clauses": (
                len(contrato.clauses)
                if contrato is not None
                else 0
            ),
            "analyzed_clauses": len(resultados),
            "successful_clauses": exitosas,
            "failed_clauses": (
                len(resultados) - exitosas
            ),
            "results": resultados,
            "errors": estado["errors"],
            "attempts": estado["attempts"],
        }
    )
