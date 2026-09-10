import os
from time import perf_counter

import httpx
import pytest

E2E_ENABLED = os.getenv("RUN_E2E") == "1"
BASE_URL = os.getenv(
    "E2E_BASE_URL",
    "http://127.0.0.1",
).rstrip("/")
TERMS_URL = os.getenv(
    "E2E_TERMS_URL",
    "https://example.com",
)
TIMEOUT_SECONDS = float(os.getenv("E2E_TIMEOUT_SECONDS", "1800"))

pytestmark = pytest.mark.skipif(
    not E2E_ENABLED,
    reason="Defina RUN_E2E=1 para ejecutar la prueba real.",
)


def test_gateway_y_backend_estan_disponibles() -> None:
    """Comprueba el acceso a FastAPI a través de Traefik."""

    response = httpx.get(
        f"{BASE_URL}/health",
        timeout=30.0,
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "backend",
    }


def test_gateway_rechaza_url_invalida() -> None:
    """Comprueba la validación HTTP antes de iniciar LangGraph."""

    response = httpx.post(
        f"{BASE_URL}/analisis",
        json={"url": "url-invalida"},
        timeout=30.0,
    )

    assert response.status_code == 422


def test_pipeline_completo_desde_traefik() -> None:
    """Ejecuta el recorrido real hasta obtener resultados por cláusula."""

    started = perf_counter()
    response = httpx.post(
        f"{BASE_URL}/analisis",
        json={"url": TERMS_URL},
        timeout=TIMEOUT_SECONDS,
    )
    duration = perf_counter() - started

    print(
        f"E2E_DURATION_SECONDS={duration:.2f}",
        flush=True,
    )

    assert response.status_code == 200
    body = response.json()

    assert body["status"] in {
        "success",
        "partial",
    }
    assert body["source_url"]
    assert body["platform"]

    total = body["total_clauses"]
    analyzed = body["analyzed_clauses"]
    successful = body["successful_clauses"]
    failed = body["failed_clauses"]
    results = body["results"]

    assert isinstance(total, int)
    assert total > 0
    assert analyzed == total
    assert successful + failed == analyzed
    assert len(results) == analyzed

    expected_status = "success" if failed == 0 else "partial"
    assert body["status"] == expected_status

    orders = [item["clause_order"] for item in results]
    assert orders == sorted(set(orders))

    for item in results:
        assert item["status"] in {
            "success",
            "error",
        }

        if item["status"] == "error":
            assert item["error"]
            continue

        assessment = item["result"]
        assert assessment["analysis_status"] in {
            "classified",
            "requires_review",
        }
        assert assessment["relevant_fragment"]
        assert assessment["justification"]
        assert assessment["recommendation"]

        if assessment["analysis_status"] == "classified":
            assert assessment["classification"] in {
                "fair",
                "potentially_abusive",
                "abusive",
            }
            assert assessment["risk_level"] in {
                "low",
                "medium",
                "high",
            }
            assert assessment["legal_basis"]
        else:
            assert assessment["classification"] is None
            assert assessment["risk_level"] is None
            assert assessment["requires_human_review"] is True
