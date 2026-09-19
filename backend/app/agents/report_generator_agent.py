from app.schemas.report import (
    AnalysisReport,
    ReportGenerationRequest,
    ReportGenerationResponse,
    RiskSummary,
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

    risk_summary = RiskSummary()

    for item in clauses:
        assessment = item.analysis.result

        if assessment is None:
            continue

        if assessment.analysis_status == "requires_review":
            risk_summary.requires_review += 1
            continue

        if assessment.risk_level == "low":
            risk_summary.low += 1
        elif assessment.risk_level == "medium":
            risk_summary.medium += 1
        elif assessment.risk_level == "high":
            risk_summary.high += 1

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
        risk_summary=risk_summary,
        clauses=clauses,
    )

    return ReportGenerationResponse(
        status="success",
        report=report,
    )
