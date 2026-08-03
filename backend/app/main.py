from fastapi import FastAPI

from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    description=(
        "API para la detección de cláusulas potencialmente abusivas "
        "mediante un sistema multiagente con enfoque LLMOps."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)
