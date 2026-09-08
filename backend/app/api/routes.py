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

    return jsonable_encoder(estado)
