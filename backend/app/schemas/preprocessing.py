from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class ProcessedClause(BaseModel):
    """Representa una cláusula obtenida del contrato."""

    order: int = Field(ge=1)
    original_order: int = Field(ge=1)
    heading: str | None = None
    heading_level: int | None = Field(
        default=None,
        ge=1,
        le=6,
    )
    content: str = Field(min_length=1)


class RemovedBlock(BaseModel):
    """Representa un bloque eliminado durante la limpieza."""

    original_order: int = Field(ge=1)
    content: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class PreprocessedContract(BaseModel):
    """Representa el contrato limpio y segmentado."""

    source_url: HttpUrl
    platform: str
    title: str
    language: str
    cleaned_text: str
    clauses: list[ProcessedClause]
    removed_blocks: list[RemovedBlock]


class PreprocessingResponse(BaseModel):
    """Representa la respuesta final del Agente Preprocesador."""

    status: Literal["success", "error"]
    result: PreprocessedContract | None = None
    error: str | None = None
