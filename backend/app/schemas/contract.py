from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class ExtractionRequest(BaseModel):
    """Datos necesarios para solicitar una extracción."""

    url: HttpUrl
    platform: str | None = None


class ContractSection(BaseModel):
    """Sección identificada dentro de un contrato."""

    order: int = Field(ge=1)
    heading: str | None = None
    content: str = Field(min_length=1)


class ExtractedContract(BaseModel):
    """Contrato obtenido desde una plataforma SaaS."""

    source_url: HttpUrl
    platform: str
    title: str
    retrieved_at: datetime
    extraction_method: Literal["beautiful_soup", "playwright"]
    language: str
    sections: list[ContractSection]
    full_text: str


class ExtractionResponse(BaseModel):
    """Resultado general de la extracción."""

    status: Literal["success", "error"]
    contract: ExtractedContract | None = None
    error: str | None = None
