from types import SimpleNamespace
from uuid import uuid4

from app.api import routes
from app.main import app
from app.schemas.contract import ExtractionRequest
from app.schemas.observability import ObservabilitySummary
from app.schemas.report import AnalysisReport, ClassificationSummary
from fastapi.testclient import TestClient

client = TestClient(app)


def test_root() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["message"] == ("Sistema Multiagente LLMOps")


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_llmops_dashboard(
    monkeypatch,
) -> None:
    recibido: dict[str, int] = {}

    def listar(
        *,
        limit: int,
    ) -> list[object]:
        recibido["limit"] = limit
        return []

    monkeypatch.setattr(
        routes,
        "list_recent_observability_runs",
        listar,
    )

    response = client.get(
        "/llmops?limit=25"
    )

    assert response.status_code == 200
    assert recibido["limit"] == 25

    assert response.json() == {
        "total_executions": 0,
        "average_latency_ms": 0.0,
        "total_tokens": 0,
        "total_cost_usd": None,
        "error_rate_percent": 0.0,
        "total_errors": 0,
        "executions": [],
    }


def test_analisis_ejecuta_pipeline(
    monkeypatch,
) -> None:
    datos_recibidos: dict[str, object] = {}

    def ejecutar(
        request: ExtractionRequest,
    ) -> dict[str, object]:
        datos_recibidos["url"] = str(request.url)
        datos_recibidos["platform"] = request.platform

        return {
            "execution_id": "ejecucion-prueba",
            "request": request,
            "status": "success",
            "reused_analysis": False,
            "reused_analysis_at": None,
            "current_step": "finalization",
            "extracted_contract": None,
            "preprocessed_contract": None,
            "current_clause_index": 0,
            "knowledge_response": None,
            "clause_results": {},
            "observability_summary": ObservabilitySummary(
                status="success",
                duration_ms=1250.0,
                prompt_tokens=100,
                completion_tokens=25,
                total_tokens=125,
                cost_usd=0.0035,
                error_count=0,
                llm_invocation_count=1,
            ),
            "errors": [],
            "attempts": {},
        }

    monkeypatch.setattr(
        routes,
        "ejecutar_orquestacion",
        ejecutar,
    )

    response = client.post(
        "/analisis",
        json={
            "url": "https://example.com/terms",
            "platform": "Example",
        },
    )

    assert response.status_code == 200
    assert datos_recibidos == {
        "url": "https://example.com/terms",
        "platform": "Example",
    }
    cuerpo = response.json()

    assert cuerpo["execution_id"] == ("ejecucion-prueba")
    assert cuerpo["status"] == "success"
    assert cuerpo["source_url"] == ("https://example.com/terms")
    assert cuerpo["total_clauses"] == 0
    assert cuerpo["analyzed_clauses"] == 0
    assert cuerpo["successful_clauses"] == 0
    assert cuerpo["failed_clauses"] == 0
    assert cuerpo["results"] == []
    assert cuerpo["report"] is None
    assert cuerpo["observability_summary"] == {
        "status": "success",
        "duration_ms": 1250.0,
        "prompt_tokens": 100,
        "completion_tokens": 25,
        "total_tokens": 125,
        "cost_usd": 0.0035,
        "error_count": 0,
        "llm_invocation_count": 1,
    }
    assert "extracted_contract" not in cuerpo
    assert "preprocessed_contract" not in cuerpo



def test_analisis_usa_informe_generado(
    monkeypatch,
) -> None:
    def ejecutar(
        request: ExtractionRequest,
    ) -> dict[str, object]:
        return {
            "execution_id": "ejecucion-informe",
            "request": request,
            "status": "success",
            "reused_analysis": False,
            "reused_analysis_at": None,
            "current_step": "finalization",
            "extracted_contract": None,
            "preprocessed_contract": None,
            "report": AnalysisReport(
                execution_id="ejecucion-informe",
                source_url="https://report.example.com/terms",
                platform="Report Platform",
                title="Terms",
                language="es",
                total_clauses=0,
                analyzed_clauses=0,
                successful_clauses=0,
                failed_clauses=0,
                classification_summary=ClassificationSummary(),
                clauses=[],
            ),
            "current_clause_index": 0,
            "knowledge_response": None,
            "clause_results": {},
            "observability_summary": ObservabilitySummary(
                status="success",
                duration_ms=1250.0,
                prompt_tokens=100,
                completion_tokens=25,
                total_tokens=125,
                cost_usd=0.0035,
                error_count=0,
                llm_invocation_count=1,
            ),
            "errors": [],
            "attempts": {},
        }

    monkeypatch.setattr(
        routes,
        "ejecutar_orquestacion",
        ejecutar,
    )

    response = client.post(
        "/analisis",
        json={
            "url": "https://request.example.com/terms",
            "platform": "Request Platform",
        },
    )

    assert response.status_code == 200

    cuerpo = response.json()

    assert cuerpo["execution_id"] == "ejecucion-informe"
    assert cuerpo["source_url"] == (
        "https://report.example.com/terms"
    )
    assert cuerpo["platform"] == "Report Platform"
    assert cuerpo["total_clauses"] == 0
    assert cuerpo["analyzed_clauses"] == 0
    assert cuerpo["successful_clauses"] == 0
    assert cuerpo["failed_clauses"] == 0
    assert cuerpo["results"] == []
    assert cuerpo["report"]["execution_id"] == (
        "ejecucion-informe"
    )
    assert cuerpo["report"]["classification_summary"] == {
        "not_potentially_abusive": 0,
        "potentially_abusive": 0,
        "strong_indications_of_abusiveness": 0,
        "not_applicable": 0,
    }
    assert cuerpo["observability_summary"]["total_tokens"] == 125
    assert cuerpo["observability_summary"]["cost_usd"] == 0.0035



def test_recupera_analisis_por_execution_id(
    monkeypatch,
) -> None:
    execution_id = uuid4()

    informe = AnalysisReport(
        execution_id=str(execution_id),
        source_url="https://example.com/terms",
        platform="Example",
        title="Terms of Service",
        language="es",
        total_clauses=0,
        analyzed_clauses=0,
        successful_clauses=0,
        failed_clauses=0,
        classification_summary=ClassificationSummary(),
        clauses=[],
    )

    registro = SimpleNamespace(
        execution_id=execution_id,
        status="success",
        report_data=informe.model_dump(
            mode="json"
        ),
        errors=[],
        attempts={},
    )

    monkeypatch.setattr(
        routes,
        "get_analysis_by_execution_id",
        lambda _execution_id: registro,
    )

    response = client.get(
        f"/analisis/{execution_id}"
    )

    assert response.status_code == 200

    cuerpo = response.json()

    assert cuerpo["execution_id"] == str(execution_id)
    assert cuerpo["status"] == "success"
    assert cuerpo["source_url"] == (
        "https://example.com/terms"
    )
    assert cuerpo["platform"] == "Example"
    assert cuerpo["total_clauses"] == 0
    assert cuerpo["results"] == []
    assert cuerpo["errors"] == []
    assert cuerpo["attempts"] == {}
    assert cuerpo["report"]["execution_id"] == (
        str(execution_id)
    )


def test_recuperar_analisis_inexistente_devuelve_404(
    monkeypatch,
) -> None:
    execution_id = uuid4()

    monkeypatch.setattr(
        routes,
        "get_analysis_by_execution_id",
        lambda _execution_id: None,
    )

    response = client.get(
        f"/analisis/{execution_id}"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "No se encontró un análisis asociado "
        "al identificador indicado."
    )


def crear_informe_vacio() -> AnalysisReport:
    return AnalysisReport(
        execution_id="ejecucion-exportacion",
        source_url="https://example.com/terms",
        platform="Example",
        title="Terms of Service",
        language="es",
        total_clauses=0,
        analyzed_clauses=0,
        successful_clauses=0,
        failed_clauses=0,
        classification_summary=ClassificationSummary(),
        clauses=[],
    )


def test_exporta_informe_json() -> None:
    response = client.post(
        "/reportes/json",
        json=crear_informe_vacio().model_dump(
            mode="json"
        ),
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/json"
    )
    assert response.headers["content-disposition"] == (
        'attachment; filename="informe_analisis.json"'
    )
    assert response.json()["execution_id"] == (
        "ejecucion-exportacion"
    )


def test_exporta_informe_pdf() -> None:
    response = client.post(
        "/reportes/pdf",
        json=crear_informe_vacio().model_dump(
            mode="json"
        ),
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == (
        "application/pdf"
    )
    assert response.headers["content-disposition"] == (
        'attachment; filename="informe_analisis.pdf"'
    )
    assert response.content.startswith(b"%PDF")
