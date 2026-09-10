from app.api import routes
from app.main import app
from app.schemas.contract import ExtractionRequest
from app.schemas.legal_corpus import Jurisdiction
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
        jurisdiction: Jurisdiction,
    ) -> dict[str, object]:
        datos_recibidos["url"] = str(request.url)
        datos_recibidos["platform"] = request.platform
        datos_recibidos["jurisdiction"] = jurisdiction

        return {
            "execution_id": "ejecucion-prueba",
            "request": request,
            "jurisdiction": jurisdiction,
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
        "/analisis?jurisdiction=ecuador",
        json={
            "url": "https://example.com/terms",
            "platform": "Example",
        },
    )

    assert response.status_code == 200
    assert datos_recibidos == {
        "url": "https://example.com/terms",
        "platform": "Example",
        "jurisdiction": "ecuador",
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
    assert "extracted_contract" not in cuerpo
    assert "preprocessed_contract" not in cuerpo
