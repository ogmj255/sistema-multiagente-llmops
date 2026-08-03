from fastapi import APIRouter

router = APIRouter()


@router.get("/", tags=["General"])
def root() -> dict[str, str]:
    """Muestra información general de la API."""
    return {
        "message": "Sistema Multiagente LLMOps",
        "version": "0.1.0",
    }


@router.get("/health", tags=["Health"])
def health() -> dict[str, str]:
    """Comprueba que el servicio está funcionando."""
    return {
        "status": "ok",
        "service": "backend",
    }
