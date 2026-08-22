from typing import Literal, Self

from pydantic import (
    BaseModel,
    Field,
    HttpUrl,
    model_validator,
)


class ProcessedClause(BaseModel):
    """Representa una cláusula obtenida del contrato."""

    order: int = Field(ge=1)
    original_order: int = Field(ge=1)
    heading: str | None = Field(
        default=None,
        min_length=1,
    )
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
    platform: str = Field(min_length=1)
    title: str = Field(min_length=1)
    language: str = Field(min_length=1)
    cleaned_text: str = Field(min_length=1)
    clauses: list[ProcessedClause] = Field(
        min_length=1,
    )
    removed_blocks: list[RemovedBlock]


class PreprocessingResponse(BaseModel):
    """Representa la respuesta final del Agente Preprocesador."""

    status: Literal["success", "error"]
    result: PreprocessedContract | None = None
    error: str | None = Field(
        default=None,
        min_length=1,
    )

    @model_validator(mode="after")
    def validate_status_content(self) -> Self:
        """Comprueba la coherencia entre estado, resultado y error."""

        if self.status == "success":
            if self.result is None:
                raise ValueError(
                    "Una respuesta exitosa debe contener un resultado."
                )
            if self.error is not None:
                raise ValueError(
                    "Una respuesta exitosa no puede contener un error."
                )

        if self.status == "error":
            if self.result is not None:
                raise ValueError(
                    "Una respuesta de error no puede contener un resultado."
                )
            if self.error is None:
                raise ValueError(
                    "Una respuesta de error debe contener un mensaje."
                )

        return self
