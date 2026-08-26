from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.schemas.legal_corpus import (
    BindingLevel,
    Jurisdiction,
    LegalDocumentStatus,
    LegalDocumentType,
)


class LegalChunk(BaseModel):
    """Segmento jurídico preparado para recuperación semántica."""

    chunk_id: str = Field(
        pattern=r"^[a-z0-9][a-z0-9_-]*_chunk_\d{4,}$"
    )
    document_id: str = Field(min_length=1)
    chunk_index: int = Field(ge=0)
    content: str = Field(min_length=1, max_length=1200)
    title: str = Field(min_length=1)
    jurisdiction: Jurisdiction
    issuing_body: str = Field(min_length=1)
    document_type: LegalDocumentType
    binding_level: BindingLevel
    status: LegalDocumentStatus
    language: str = Field(min_length=2)
    source_url: HttpUrl
    official_citation: str | None = None
    publication_date: date | None = None
    effective_date: date | None = None
    topics: str = Field(min_length=1)
    checksum: str = Field(pattern=r"^[a-f0-9]{64}$")


class KnowledgeQuery(BaseModel):
    """Consulta enviada al Agente de Conocimiento Jurídico."""

    model_config = ConfigDict(
        str_strip_whitespace=True
    )

    query: str = Field(min_length=3)
    top_k: int = Field(default=5, ge=1, le=20)
    jurisdiction: Jurisdiction | None = None
    document_type: LegalDocumentType | None = None


class LegalKnowledgeMatch(LegalChunk):
    """Segmento jurídico recuperado desde ChromaDB."""

    distance: float = Field(ge=0)


class KnowledgeResponse(BaseModel):
    """Respuesta estructurada del agente jurídico."""

    status: Literal["success", "error"]
    query: str
    matches: list[LegalKnowledgeMatch] = Field(
        default_factory=list
    )
    error: str | None = None


class KnowledgeIndexResponse(BaseModel):
    """Resultado de preparar e indexar el corpus jurídico."""

    status: Literal["success", "partial", "error"]
    documents: int = Field(ge=0)
    chunks: int = Field(ge=0)
    errors: list[str] = Field(default_factory=list)