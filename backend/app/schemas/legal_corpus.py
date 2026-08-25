from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl

Jurisdiction = Literal[
    "ecuador",
    "european_union",
    "international",
]

LegalDocumentType = Literal[
    "constitution",
    "code",
    "law",
    "regulation",
    "decree",
    "resolution",
    "directive",
    "convention",
    "guideline",
    "jurisprudence",
]

BindingLevel = Literal[
    "binding",
    "jurisprudential",
    "reference",
]

LegalDocumentStatus = Literal[
    "in_force",
    "amended",
    "repealed",
    "unknown",
]


class LegalSource(BaseModel):
    """Representa una fuente jurídica oficial."""

    document_id: str = Field(
        min_length=1,
        pattern=r"^[a-z0-9][a-z0-9_-]*$",
    )
    title: str = Field(min_length=1)
    jurisdiction: Jurisdiction
    issuing_body: str = Field(min_length=1)
    document_type: LegalDocumentType
    binding_level: BindingLevel
    status: LegalDocumentStatus
    language: str = Field(min_length=2)
    source_url: HttpUrl
    topics: list[str] = Field(min_length=1)
    official_citation: str | None = None
    publication_date: date | None = None
    effective_date: date | None = None


class LegalDocument(BaseModel):
    """Representa un documento jurídico procesado."""

    source: LegalSource
    retrieved_at: datetime
    content_type: str = Field(min_length=1)
    checksum: str = Field(
        pattern=r"^[a-f0-9]{64}$",
    )
    content: str = Field(min_length=1)
    raw_path: str = Field(min_length=1)
    processed_path: str = Field(min_length=1)


class CorpusBuildError(BaseModel):
    """Registra un documento que no pudo procesarse."""

    document_id: str = Field(min_length=1)
    source_url: HttpUrl
    error: str = Field(min_length=1)


class CorpusBuildResult(BaseModel):
    """Resume la construcción del corpus jurídico."""

    requested: int = Field(ge=0)
    completed: int = Field(ge=0)
    failed: int = Field(ge=0)
    documents: list[LegalDocument]
    errors: list[CorpusBuildError]