from fastapi import APIRouter, Response
from fastapi.encoders import jsonable_encoder

from app.agents.orquestador import ejecutar_orquestacion
from app.schemas.contract import ExtractionRequest
from app.schemas.report import AnalysisReport
from app.services.report_export import (
    export_report_json,
    export_report_pdf,
)

router = APIRouter()


@router.get("/", tags=["General"])
def root() -> dict[str, str]:
    """Muestra informacion general de la API."""
    return {
        "message": "Sistema Multiagente LLMOps",
        "version": "0.1.0",
    }


@router.get("/health", tags=["Health"])
def health() -> dict[str, str]:
    """Comprueba que el servicio esta funcionando."""
    return {
        "status": "ok",
        "service": "backend",
    }


@router.post("/analisis", tags=["Analisis"])
def analizar_terminos(
    request: ExtractionRequest,
) -> dict[str, object]:
    """Ejecuta el pipeline desde una URL de terminos."""

    estado = ejecutar_orquestacion(request)
    informe = estado.get("report")

    if informe is not None:
        resultados = [
            {
                "clause_order": item.clause_order,
                **jsonable_encoder(item.analysis),
            }
            for item in informe.clauses
        ]

        source_url = informe.source_url
        platform = informe.platform
        total_clauses = informe.total_clauses
        analyzed_clauses = informe.analyzed_clauses
        successful_clauses = informe.successful_clauses
        failed_clauses = informe.failed_clauses
    else:
        respuestas = estado["clause_results"]
        resultados = [
            {
                "clause_order": orden,
                **jsonable_encoder(respuesta),
            }
            for orden, respuesta in sorted(
                respuestas.items()
            )
        ]

        exitosas = sum(
            respuesta.status == "success"
            for respuesta in respuestas.values()
        )
        contrato = estado["preprocessed_contract"]

        source_url = request.url
        platform = (
            contrato.platform
            if contrato is not None
            else request.platform
        )
        total_clauses = (
            len(contrato.clauses)
            if contrato is not None
            else 0
        )
        analyzed_clauses = len(resultados)
        successful_clauses = exitosas
        failed_clauses = len(resultados) - exitosas

    return jsonable_encoder(
        {
            "execution_id": estado["execution_id"],
            "status": estado["status"],
            "source_url": source_url,
            "platform": platform,
            "total_clauses": total_clauses,
            "analyzed_clauses": analyzed_clauses,
            "successful_clauses": successful_clauses,
            "failed_clauses": failed_clauses,
            "results": resultados,
            "report": informe,
            "errors": estado["errors"],
            "attempts": estado["attempts"],
        }
    )



@router.post("/reportes/json", tags=["Reportes"])
def descargar_informe_json(
    report: AnalysisReport,
) -> Response:
    """Descarga el informe estructurado en formato JSON."""

    return Response(
        content=export_report_json(report),
        media_type="application/json",
        headers={
            "Content-Disposition": (
                'attachment; filename="informe_analisis.json"'
            )
        },
    )


@router.post("/reportes/pdf", tags=["Reportes"])
def descargar_informe_pdf(
    report: AnalysisReport,
) -> Response:
    """Descarga el informe estructurado en formato PDF."""

    return Response(
        content=export_report_pdf(report),
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                'attachment; filename="informe_analisis.pdf"'
            )
        },
    )
