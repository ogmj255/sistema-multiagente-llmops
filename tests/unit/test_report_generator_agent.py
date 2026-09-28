from app.agents.report_generator_agent import (
    run_report_generator_agent,
)
from app.schemas.knowledge import LegalKnowledgeMatch
from app.schemas.legal_analysis import (
    ClauseAnalysisResponse,
    ClauseAssessment,
)
from app.schemas.report import (
    ClauseReportItem,
    ReportGenerationRequest,
)


def crear_evidencia() -> LegalKnowledgeMatch:
    """Crea evidencia jurídica para las pruebas."""

    return LegalKnowledgeMatch(
        chunk_id="ec_ley_chunk_0001",
        document_id="ec_ley",
        chunk_index=0,
        content="Normativa jurídica de prueba.",
        title="Ley de prueba",
        jurisdiction="ecuador",
        issuing_body="Asamblea Nacional",
        document_type="law",
        binding_level="binding",
        status="in_force",
        language="es",
        source_url="https://example.com/ley",
        topics="contratos",
        checksum="a" * 64,
        distance=0.1,
    )


def crear_analisis(
    classification: str,
) -> ClauseAnalysisResponse:
    """Crea un análisis contractual clasificado."""

    return ClauseAnalysisResponse(
        status="success",
        result=ClauseAssessment(
            category="Condiciones contractuales",
            clause_type="Disposición contractual",
            target="Usuario",
            consequence="Produce efectos sobre el usuario.",
            classification=classification,
            analysis_status="classified",
            relevant_fragment="Contenido contractual.",
            justification="Justificación de prueba.",
            recommendation="Recomendación de prueba.",
            evidence_sufficiency="sufficient",
            legal_basis=[crear_evidencia()],
        ),
    )


def crear_no_aplicable() -> ClauseAnalysisResponse:
    """Crea un resultado para un fragmento no sustantivo."""

    return ClauseAnalysisResponse(
        status="success",
        result=ClauseAssessment(
            category="Encabezado contractual",
            clause_type="Título sin contenido normativo",
            target="No aplica",
            consequence=None,
            classification=None,
            analysis_status="not_applicable",
            relevant_fragment="Condiciones generales",
            justification=(
                "El fragmento corresponde únicamente "
                "a un encabezado."
            ),
            recommendation=None,
            evidence_sufficiency="insufficient",
            legal_basis=[],
        ),
    )


def test_genera_resumen_y_ordena_clausulas() -> None:
    request = ReportGenerationRequest(
        execution_id="ejecucion-1",
        source_url="https://example.com/terms",
        platform="Example",
        title="Terms of Service",
        language="es",
        total_clauses=5,
        clauses=[
            ClauseReportItem(
                clause_order=5,
                analysis=ClauseAnalysisResponse(
                    status="error",
                    error="Falló el análisis.",
                ),
            ),
            ClauseReportItem(
                clause_order=3,
                analysis=crear_analisis(
                    "strong_indications_of_abusiveness"
                ),
            ),
            ClauseReportItem(
                clause_order=1,
                analysis=crear_analisis(
                    "not_potentially_abusive"
                ),
            ),
            ClauseReportItem(
                clause_order=4,
                analysis=crear_no_aplicable(),
            ),
            ClauseReportItem(
                clause_order=2,
                analysis=crear_analisis(
                    "potentially_abusive"
                ),
            ),
        ],
    )

    response = run_report_generator_agent(request)

    assert response.status == "success"
    assert response.error is None
    assert response.report is not None

    report = response.report

    assert report.total_clauses == 5
    assert report.analyzed_clauses == 5
    assert report.successful_clauses == 4
    assert report.failed_clauses == 1

    summary = report.classification_summary

    assert summary.not_potentially_abusive == 1
    assert summary.potentially_abusive == 1
    assert summary.strong_indications_of_abusiveness == 1
    assert summary.not_applicable == 1

    assert [
        item.clause_order
        for item in report.clauses
    ] == [1, 2, 3, 4, 5]
