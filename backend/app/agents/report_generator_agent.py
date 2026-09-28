from app.schemas.report import (
    AnalysisReport,
    ClassificationSummary,
    ReportGenerationRequest,
    ReportGenerationResponse,
)


def run_report_generator_agent(
    request: ReportGenerationRequest,
) -> ReportGenerationResponse:
    """Genera un informe estructurado desde los análisis existentes."""

    clauses = sorted(
        request.clauses,
        key=lambda item: item.clause_order,
    )

    successful_clauses = sum(
        item.analysis.status == "success"
        for item in clauses
    )
    failed_clauses = len(clauses) - successful_clauses

    classification_summary = ClassificationSummary()

    for item in clauses:
        assessment = item.analysis.result

        if assessment is None:
            continue


        if assessment.analysis_status == "not_applicable":
            classification_summary.not_applicable += 1
            continue

        if assessment.classification == "not_potentially_abusive":
            classification_summary.not_potentially_abusive += 1
        elif assessment.classification == "potentially_abusive":
            classification_summary.potentially_abusive += 1
        elif (
            assessment.classification
            == "strong_indications_of_abusiveness"
        ):
            classification_summary.strong_indications_of_abusiveness += 1

    report = AnalysisReport(
        execution_id=request.execution_id,
        source_url=request.source_url,
        platform=request.platform,
        title=request.title,
        language=request.language,
        total_clauses=request.total_clauses,
        analyzed_clauses=len(clauses),
        successful_clauses=successful_clauses,
        failed_clauses=failed_clauses,
        classification_summary=classification_summary,
        clauses=clauses,
    )

    return ReportGenerationResponse(
        status="success",
        report=report,
    )
