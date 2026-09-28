from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.encoders import jsonable_encoder

from app.agents.orchestrator_agent import ejecutar_orquestacion
from app.schemas.contract import ExtractionRequest
from app.schemas.observability import LLMOpsDashboardResponse
from app.schemas.report import AnalysisReport
from app.services.analysis_persistence import (
    get_analysis_by_execution_id,
)
from app.services.observability_dashboard import (
    build_llmops_dashboard,
)
from app.services.observability_persistence import (
    list_recent_observability_runs,
)
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
            "reused_analysis": estado["reused_analysis"],
            "reused_analysis_at": estado["reused_analysis_at"],
            "source_url": source_url,
            "platform": platform,
            "total_clauses": total_clauses,
            "analyzed_clauses": analyzed_clauses,
            "successful_clauses": successful_clauses,
            "failed_clauses": failed_clauses,
            "results": resultados,
            "report": informe,
            "observability_summary": estado[
                "observability_summary"
            ],
            "errors": estado["errors"],
            "attempts": estado["attempts"],
        }
    )



@router.get(
    "/analisis/{execution_id}",
    tags=["Analisis"],
)
def obtener_analisis(
    execution_id: UUID,
) -> dict[str, object]:
    """Recupera un an?lisis persistido mediante su identificador."""

    registro = get_analysis_by_execution_id(
        execution_id
    )

    if registro is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "No se encontró un análisis asociado "
                "al identificador indicado."
            ),
        )

    informe = AnalysisReport.model_validate(
        registro.report_data
    )

    resultados = [
        {
            "clause_order": item.clause_order,
            **jsonable_encoder(item.analysis),
        }
        for item in informe.clauses
    ]

    return jsonable_encoder(
        {
            "execution_id": str(registro.execution_id),
            "status": registro.status,
            "source_url": informe.source_url,
            "platform": informe.platform,
            "total_clauses": informe.total_clauses,
            "analyzed_clauses": informe.analyzed_clauses,
            "successful_clauses": informe.successful_clauses,
            "failed_clauses": informe.failed_clauses,
            "results": resultados,
            "report": informe,
            "errors": registro.errors,
            "attempts": registro.attempts,
        }
    )


@router.get(
    "/llmops",
    tags=["LLMOps"],
    response_model=LLMOpsDashboardResponse,
)
def obtener_dashboard_llmops(
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
    ),
) -> LLMOpsDashboardResponse:
    """Devuelve métricas históricas reales para el dashboard."""

    runs = list_recent_observability_runs(
        limit=limit
    )

    return build_llmops_dashboard(
        runs
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
