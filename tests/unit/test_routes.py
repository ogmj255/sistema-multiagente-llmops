from app.api import routes
from app.main import app
from app.schemas.contract import ExtractionRequest
from app.schemas.report import AnalysisReport, RiskSummary
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
            "current_step": "finalization",
            "extracted_contract": None,
            "preprocessed_contract": None,
            "current_clause_index": 0,
            "knowledge_response": None,
            "clause_results": {},
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
                risk_summary=RiskSummary(),
                clauses=[],
            ),
            "current_clause_index": 0,
            "knowledge_response": None,
            "clause_results": {},
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
    assert cuerpo["report"]["risk_summary"] == {
        "low": 0,
        "medium": 0,
        "high": 0,
        "requires_review": 0,
    }



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
        risk_summary=RiskSummary(),
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
