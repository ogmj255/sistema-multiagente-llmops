import json
from io import BytesIO

from app.schemas.knowledge import LegalKnowledgeMatch
from app.schemas.legal_analysis import (
    ClauseAnalysisResponse,
    ClauseAssessment,
)
from app.schemas.report import (
    AnalysisReport,
    ClauseReportItem,
    RiskSummary,
)
from app.services.report_export import (
    export_report_json,
    export_report_pdf,
)
from pypdf import PdfReader


def crear_informe() -> AnalysisReport:
    evidencia = LegalKnowledgeMatch(
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

    analisis = ClauseAnalysisResponse(
        status="success",
        result=ClauseAssessment(
            category="limitation_of_liability",
            classification="potentially_abusive",
            risk_level="medium",
            analysis_status="classified",
            relevant_fragment="La responsabilidad podrá limitarse.",
            justification="La cláusula requiere revisión jurídica.",
            recommendation="Revisar el alcance de la limitación.",
            evidence_sufficiency="partial",
            legal_basis=[evidencia],
        ),
    )

    return AnalysisReport(
        execution_id="ejecucion-1",
        source_url="https://example.com/terms",
        platform="Example",
        title="Terms of Service",
        language="es",
        total_clauses=1,
        analyzed_clauses=1,
        successful_clauses=1,
        failed_clauses=0,
        risk_summary=RiskSummary(
            medium=1,
        ),
        clauses=[
            ClauseReportItem(
                clause_order=1,
                analysis=analisis,
            )
        ],
    )


def test_exporta_informe_json() -> None:
    contenido = export_report_json(
        crear_informe()
    )

    datos = json.loads(
        contenido.decode("utf-8")
    )

    assert datos["execution_id"] == "ejecucion-1"
    assert datos["platform"] == "Example"
    assert datos["risk_summary"]["medium"] == 1
    assert datos["clauses"][0]["clause_order"] == 1


def test_exporta_informe_pdf_legible() -> None:
    contenido = export_report_pdf(
        crear_informe()
    )

    assert contenido.startswith(b"%PDF")

    reader = PdfReader(
        BytesIO(contenido)
    )
    texto = "\n".join(
        page.extract_text() or ""
        for page in reader.pages
    )

    assert "Informe de análisis contractual" in texto
    assert "Example" in texto
    assert "Cláusula 1" in texto
    assert "La cláusula requiere revisión jurídica." in texto
