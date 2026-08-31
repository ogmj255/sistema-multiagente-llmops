from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    model_validator,
)

from app.schemas.knowledge import LegalKnowledgeMatch
from app.schemas.legal_corpus import Jurisdiction
from app.schemas.preprocessing import ProcessedClause

ClauseCategory = Literal[
    "privacy_and_data_processing",
    "data_transfer_to_third_parties",
    "unilateral_modification",
    "unilateral_termination",
    "limitation_of_liability",
    "dispute_resolution",
    "consumer_rights_restriction",
    "user_content_and_intellectual_property",
    "other_contractual_risk",
]

ClauseClassification = Literal[
    "fair",
    "potentially_abusive",
    "abusive",
]

RiskLevel = Literal[
    "low",
    "medium",
    "high",
]

EvidenceSufficiency = Literal[
    "sufficient",
    "partial",
    "insufficient",
]

AnalysisStatus = Literal[
    "classified",
    "requires_review",
]

RISK_BY_CLASSIFICATION: dict[
    ClauseClassification,
    RiskLevel,
] = {
    "fair": "low",
    "potentially_abusive": "medium",
    "abusive": "high",
}


class ClauseAnalysisRequest(BaseModel):
    """Entrada para analizar una cláusula contractual."""

    model_config = ConfigDict(
        str_strip_whitespace=True
    )

    source_url: HttpUrl
    platform: str = Field(min_length=1)
    language: str = Field(min_length=2)
    jurisdiction: Jurisdiction = "ecuador"
    clause: ProcessedClause


class ClauseAssessment(BaseModel):
    """Valoración jurídica automatizada de una cláusula."""

    model_config = ConfigDict(
        str_strip_whitespace=True
    )

    category: ClauseCategory
    classification: ClauseClassification | None = None
    risk_level: RiskLevel | None = None
    analysis_status: AnalysisStatus
    relevant_fragment: str = Field(min_length=1)
    justification: str = Field(min_length=1)
    recommendation: str = Field(min_length=1)
    evidence_sufficiency: EvidenceSufficiency
    requires_human_review: bool = False
    legal_basis: list[LegalKnowledgeMatch] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def validate_assessment(self) -> Self:
        """Comprueba coherencia, evidencia y riesgo."""

        if self.analysis_status == "requires_review":
            if self.classification is not None:
                raise ValueError(
                    "Un análisis inconcluso no puede "
                    "contener clasificación."
                )

            if self.risk_level is not None:
                raise ValueError(
                    "Un análisis inconcluso no puede "
                    "contener nivel de riesgo."
                )

            if self.evidence_sufficiency != "insufficient":
                raise ValueError(
                    "La revisión se utiliza cuando la "
                    "evidencia es insuficiente."
                )

            self.requires_human_review = True
            return self

        if self.classification is None:
            raise ValueError(
                "Un análisis clasificado debe contener "
                "una clasificación."
            )

        if self.evidence_sufficiency == "insufficient":
            raise ValueError(
                "No se puede clasificar con evidencia "
                "insuficiente."
            )

        expected_risk = RISK_BY_CLASSIFICATION[
            self.classification
        ]

        if self.risk_level is None:
            self.risk_level = expected_risk
        elif self.risk_level != expected_risk:
            raise ValueError(
                "El nivel de riesgo no corresponde "
                "a la clasificación."
            )

        if not self.legal_basis:
            raise ValueError(
                "Una clasificación debe contener "
                "fundamento jurídico."
            )

        if (
            self.classification == "abusive"
            and self.evidence_sufficiency != "sufficient"
        ):
            raise ValueError(
                "Una cláusula abusiva requiere evidencia "
                "jurídica suficiente."
            )

        self.requires_human_review = (
            self.classification != "fair"
            or self.evidence_sufficiency != "sufficient"
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
                raise ValueError(
                    "Una respuesta exitosa debe contener "
                    "un resultado."
                )

            if self.error is not None:
                raise ValueError(
                    "Una respuesta exitosa no puede "
                    "contener un error."
                )

        if self.status == "error":
            if self.result is not None:
                raise ValueError(
                    "Una respuesta de error no puede "
                    "contener un resultado."
                )

            if self.error is None:
                raise ValueError(
                    "Una respuesta de error debe contener "
                    "un mensaje."
                )

        return self