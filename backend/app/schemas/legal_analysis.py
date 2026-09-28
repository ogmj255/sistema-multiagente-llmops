from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    model_validator,
)

from app.schemas.knowledge import LegalKnowledgeMatch
from app.schemas.preprocessing import ProcessedClause

ClauseClassification = Literal[
    "not_potentially_abusive",
    "potentially_abusive",
    "strong_indications_of_abusiveness",
]

EvidenceSufficiency = Literal[
    "sufficient",
    "partial",
    "insufficient",
]

AnalysisStatus = Literal[
    "classified",
    "not_applicable",
]

EvidenceIndex = Annotated[
    int,
    Field(ge=0),
]


class ClauseAnalysisRequest(BaseModel):
    """Entrada para analizar una cláusula contractual."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    source_url: HttpUrl
    platform: str = Field(min_length=1)
    language: str = Field(min_length=2)
    clause: ProcessedClause


class ClauseAnalysisDecision(BaseModel):
    """Decisión estructurada generada por el LLM."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    category: str = Field(min_length=1)
    clause_type: str = Field(min_length=1)
    target: str = Field(min_length=1)
    consequence: str | None = None
    classification: ClauseClassification | None
    analysis_status: AnalysisStatus
    justification: str = Field(min_length=1)
    recommendation: str | None = None
    evidence_sufficiency: EvidenceSufficiency
    legal_basis_indices: list[EvidenceIndex]

    @model_validator(mode="after")
    def validate_decision(self) -> Self:
        """Comprueba la coherencia de la decisión del modelo."""

        if self.analysis_status == "not_applicable":
            if self.classification is not None:
                raise ValueError(
                    "Un fragmento no aplicable no puede contener clasificación."
                )

            if self.legal_basis_indices:
                raise ValueError(
                    "Un fragmento no aplicable no debe seleccionar "
                    "fundamentos jurídicos."
                )

            return self

        if self.classification is None:
            raise ValueError(
                "Una disposición contractual debe contener clasificación."
            )

        if (
            self.evidence_sufficiency in {"sufficient", "partial"}
            and not self.legal_basis_indices
        ):
            raise ValueError(
                "La evidencia suficiente o parcial debe estar "
                "vinculada a fundamentos jurídicos."
            )

        return self


class ClauseAssessment(BaseModel):
    """Valoración jurídica automatizada de una cláusula."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    category: str = Field(min_length=1)
    clause_type: str = Field(min_length=1)
    target: str = Field(min_length=1)
    consequence: str | None = None
    classification: ClauseClassification | None = None
    analysis_status: AnalysisStatus
    relevant_fragment: str = Field(min_length=1)
    justification: str = Field(min_length=1)
    recommendation: str | None = None
    evidence_sufficiency: EvidenceSufficiency
    legal_basis: list[LegalKnowledgeMatch] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_assessment(self) -> Self:
        """Comprueba la coherencia de la valoración."""

        if self.analysis_status == "not_applicable":
            if self.classification is not None:
                raise ValueError(
                    "Un fragmento no aplicable no puede contener clasificación."
                )

            return self

        if self.classification is None:
            raise ValueError(
                "Una disposición contractual debe contener clasificación."
            )

        if (
            self.evidence_sufficiency in {"sufficient", "partial"}
            and not self.legal_basis
        ):
            raise ValueError(
                "La evidencia suficiente o parcial debe contener "
                "fundamento jurídico."
            )


        return self


class ClauseAnalysisResponse(BaseModel):
    """Respuesta del futuro Agente Analizador Legal."""

    status: Literal["success", "error"]
    result: ClauseAssessment | None = None
    error: str | None = Field(
        default=None,
        min_length=1,
    )

    @model_validator(mode="after")
    def validate_status_content(self) -> Self:
        """Comprueba la coherencia de la respuesta."""

        if self.status == "success":
            if self.result is None:
                raise ValueError("Una respuesta exitosa debe contener un resultado.")

            if self.error is not None:
                raise ValueError("Una respuesta exitosa no puede contener un error.")

        if self.status == "error":
            if self.result is not None:
                raise ValueError(
                    "Una respuesta de error no puede contener un resultado."
                )

            if self.error is None:
                raise ValueError("Una respuesta de error debe contener un mensaje.")

        return self
