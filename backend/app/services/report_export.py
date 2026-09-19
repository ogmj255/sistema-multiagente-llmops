import json
from html import escape
from io import BytesIO

from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

from app.schemas.report import AnalysisReport


def export_report_json(
    report: AnalysisReport,
) -> bytes:
    """Serializa el informe completo como JSON UTF-8."""

    data = report.model_dump(
        mode="json",
    )

    return json.dumps(
        data,
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")


def _paragraph(
    label: str,
    value: object,
    style: ParagraphStyle,
) -> Paragraph:
    """Construye una línea segura para el PDF."""

    return Paragraph(
        (
            f"<b>{escape(label)}:</b> "
            f"{escape(str(value))}"
        ),
        style,
    )


def export_report_pdf(
    report: AnalysisReport,
) -> bytes:
    """Genera un PDF legible a partir del informe estructurado."""

    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title="Informe de análisis contractual",
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        spaceAfter=12,
    )
    heading_style = styles["Heading2"]
    body_style = styles["BodyText"]

    story: list[object] = [
        Paragraph(
            "Informe de análisis contractual",
            title_style,
        ),
        _paragraph(
            "Plataforma",
            report.platform,
            body_style,
        ),
        _paragraph(
            "URL",
            report.source_url,
            body_style,
        ),
        _paragraph(
            "Título",
            report.title,
            body_style,
        ),
        _paragraph(
            "Idioma",
            report.language,
            body_style,
        ),
        _paragraph(
            "Ejecución",
            report.execution_id,
            body_style,
        ),
        Spacer(1, 12),
        Paragraph(
            "Resumen",
            heading_style,
        ),
        _paragraph(
            "Cláusulas totales",
            report.total_clauses,
            body_style,
        ),
        _paragraph(
            "Cláusulas analizadas",
            report.analyzed_clauses,
            body_style,
        ),
        _paragraph(
            "Análisis exitosos",
            report.successful_clauses,
            body_style,
        ),
        _paragraph(
            "Análisis fallidos",
            report.failed_clauses,
            body_style,
        ),
        _paragraph(
            "Riesgo bajo",
            report.risk_summary.low,
            body_style,
        ),
        _paragraph(
            "Riesgo medio",
            report.risk_summary.medium,
            body_style,
        ),
        _paragraph(
            "Riesgo alto",
            report.risk_summary.high,
            body_style,
        ),
        _paragraph(
            "Requieren revisión",
            report.risk_summary.requires_review,
            body_style,
        ),
    ]

    for item in report.clauses:
        story.extend(
            [
                Spacer(1, 18),
                Paragraph(
                    f"Cláusula {item.clause_order}",
                    heading_style,
                ),
            ]
        )

        analysis = item.analysis

        _status = (
            "Exitoso"
            if analysis.status == "success"
            else "Error"
        )
        story.append(
            _paragraph(
                "Estado",
                _status,
                body_style,
            )
        )

        if analysis.result is None:
            story.append(
                _paragraph(
                    "Error",
                    analysis.error or "Error no especificado",
                    body_style,
                )
            )
            continue

        assessment = analysis.result

        story.extend(
            [
                _paragraph(
                    "Categoría",
                    assessment.category,
                    body_style,
                ),
                _paragraph(
                    "Estado del análisis",
                    assessment.analysis_status,
                    body_style,
                ),
                _paragraph(
                    "Clasificación",
                    assessment.classification or "No determinada",
                    body_style,
                ),
                _paragraph(
                    "Nivel de riesgo",
                    assessment.risk_level or "No determinado",
                    body_style,
                ),
                _paragraph(
                    "Fragmento",
                    assessment.relevant_fragment,
                    body_style,
                ),
                _paragraph(
                    "Justificación",
                    assessment.justification,
                    body_style,
                ),
                _paragraph(
                    "Recomendación",
                    assessment.recommendation,
                    body_style,
                ),
                _paragraph(
                    "Suficiencia de evidencia",
                    assessment.evidence_sufficiency,
                    body_style,
                ),
                _paragraph(
                    "Revisión humana",
                    (
                        "Sí"
                        if assessment.requires_human_review
                        else "No"
                    ),
                    body_style,
                ),
            ]
        )

        if assessment.legal_basis:
            story.append(
                Paragraph(
                    "Fundamento jurídico",
                    styles["Heading3"],
                )
            )

            for evidence in assessment.legal_basis:
                story.extend(
                    [
                        _paragraph(
                            "Documento",
                            evidence.title,
                            body_style,
                        ),
                        _paragraph(
                            "Jurisdicción",
                            evidence.jurisdiction,
                            body_style,
                        ),
                        _paragraph(
                            "Contenido",
                            evidence.content,
                            body_style,
                        ),
                    ]
                )

                if evidence.official_citation:
                    story.append(
                        _paragraph(
                            "Cita oficial",
                            evidence.official_citation,
                            body_style,
                        )
                    )

                story.append(
                    Spacer(1, 6)
                )

    document.build(story)

    return buffer.getvalue()
