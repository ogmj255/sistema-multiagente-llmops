from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    model_validator,
)

from app.schemas.legal_analysis import ClauseAnalysisResponse


class ClauseReportItem(BaseModel):
    """Resultado de análisis asociado a una cláusula."""

    clause_order: int = Field(ge=1)
    analysis: ClauseAnalysisResponse


class ReportGenerationRequest(BaseModel):
    """Entrada para generar el informe de un contrato."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    execution_id: str = Field(min_length=1)
    source_url: HttpUrl
    platform: str = Field(min_length=1)
    title: str = Field(min_length=1)
    language: str = Field(min_length=2)
    total_clauses: int = Field(ge=0)
    clauses: list[ClauseReportItem] = Field(
        default_factory=list
    )


class RiskSummary(BaseModel):
    """Resume los niveles de riesgo del análisis."""

    low: int = Field(default=0, ge=0)
    medium: int = Field(default=0, ge=0)
    high: int = Field(default=0, ge=0)
    requires_review: int = Field(default=0, ge=0)


class AnalysisReport(BaseModel):
    """Informe estructurado del análisis contractual."""

    execution_id: str = Field(min_length=1)
    source_url: HttpUrl
    platform: str = Field(min_length=1)
    title: str = Field(min_length=1)
    language: str = Field(min_length=2)

    total_clauses: int = Field(ge=0)
    analyzed_clauses: int = Field(ge=0)
    successful_clauses: int = Field(ge=0)
    failed_clauses: int = Field(ge=0)

    risk_summary: RiskSummary
    clauses: list[ClauseReportItem] = Field(
        default_factory=list
    )


class ReportGenerationResponse(BaseModel):
    """Respuesta del Agente Generador de Informes."""

    status: Literal["success", "error"]
    report: AnalysisReport | None = None
    error: str | None = Field(
        default=None,
        min_length=1,
    )

    @model_validator(mode="after")
    def validate_status_content(self) -> Self:
        """Comprueba la coherencia de la respuesta."""

        if self.status == "success":
            if self.report is None:
                raise ValueError(
                    "Una respuesta exitosa debe contener un informe."
                )

            if self.error is not None:
                raise ValueError(
                    "Una respuesta exitosa no puede contener un error."
                )

        if self.status == "error":
            if self.report is not None:
                raise ValueError(
                    "Una respuesta de error no puede contener un informe."
                )

            if self.error is None:
                raise ValueError(
                    "Una respuesta de error debe contener un mensaje."
                )

        return self
