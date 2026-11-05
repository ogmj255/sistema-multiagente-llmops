"""Prueba E2E local del módulo Streamlit/API/worker SIN llamadas a modelos.

FastAPI recibe la orden como si la hubiera enviado la interfaz;
el worker ejecuta un doble de prueba que JAMÁS consulta MCP,
OpenRouter ni Langfuse. Todo se guarda en tmp_path, no en el corpus real.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.api import experimental_routes as api
from app.evaluation.design import DOCUMENTS, make_experimental_plan
from app.evaluation.groundtruth import GroundTruth, GroundTruthUnit
from app.main import app

# Este archivo es el único que importa scripts/evaluation_worker.py desde
# tests y asegura que se utilicen SOLO rutas temporales de pytest.
from scripts import evaluation_worker as worker

CLIENT = TestClient(app)
TOKEN = "token-simulado-sin-relacion-con-credenciales-reales"
HEADERS = {"X-Experiment-Token": TOKEN}


@pytest.fixture
def synthetic_groundtruth():
    """Mismos 10 ToS y 547 unidades; contenido totalmente inventado."""
    units = []
    n = 0
    for document_id, platform, count in DOCUMENTS:
        for number in range(1, count + 1):
            n += 1
            applicability = "No aplicable" if n % 7 == 0 else "Evaluable"
            label = (
                "not_applicable" if applicability == "No aplicable"
                else "potencialmente abusiva" if n % 2
                else "no potencialmente abusiva"
            )
            units.append(
                GroundTruthUnit(
                    technical_id=f"{document_id}-U{number:03d}",
                    platform=platform,
                    original_text=f"Texto sintético {document_id} {number}",
                    applicability=applicability,
                    label=label,
                    text_sha256="a" * 64,
                )
            )
    return GroundTruth(
        units=tuple(units),
        fingerprint="b" * 64,
        source_sha256="c" * 64,
    )


@pytest.fixture
def isolated_environment(monkeypatch, tmp_path, synthetic_groundtruth):
    """Aísla 100 % de los archivos reales y bloquea ejecución implícita."""
    monkeypatch.setenv("EXPERIMENT_ADMIN_TOKEN", TOKEN)
    monkeypatch.setenv("EXPERIMENT_EXECUTION_ENABLED", "false")

    plan = make_experimental_plan(synthetic_groundtruth)
    monkeypatch.setattr(
        api, "_load", lambda: (synthetic_groundtruth, plan)
    )
    monkeypatch.setattr(api, "DATA_DIR", tmp_path)

    monkeypatch.setattr(worker, "DIRECTORY", tmp_path)
    monkeypatch.setattr(worker, "QUEUE", tmp_path / "binary_jobs")
    monkeypatch.setattr(
        worker, "RESULTS", tmp_path / "v2_binary_campaign_runs.jsonl"
    )
    monkeypatch.setattr(
        worker, "CONTEXT",
        tmp_path / "v2_binary_legal_context_snapshots.jsonl"
    )
    monkeypatch.setattr(
        worker, "CHECKPOINTS",
        tmp_path / "v2_binary_unit_checkpoints.jsonl"
    )
    monkeypatch.setattr(
        worker, "load_binary_groundtruth_v2",
        lambda _path: synthetic_groundtruth
    )
    return tmp_path, synthetic_groundtruth


def test_access_control_and_disabled_billing(isolated_environment):
    folder, _dataset = isolated_environment
    assert CLIENT.get("/experimental/overview").status_code == 403
    assert CLIENT.get("/experimental/results").status_code == 403
    assert CLIENT.post(
        "/experimental/jobs",
        json={
            "task_id": "ET01-R1",
            "accept_paid_execution": True,
        },
    ).status_code == 403

    overview = CLIENT.get(
        "/experimental/overview", headers=HEADERS
    )
    assert overview.status_code == 200
    value = overview.json()
    assert value["progress"]["counts"] == {
        "completed": 0, "failed": 0, "pending": 90,
    }
    assert value["execution_enabled"] is False
    assert len(value["tasks"]) == 90

    result = CLIENT.post(
        "/experimental/jobs",
        headers=HEADERS,
        json={
            "task_id": "ET01-R1",
            "accept_paid_execution": True,
        },
    )
    assert result.status_code == 403
    assert not (folder / "binary_jobs").exists()


def test_api_queue_worker_and_results_end_to_end_simulated(
    isolated_environment, monkeypatch,
):
    folder, dataset = isolated_environment
    monkeypatch.setenv(
        "EXPERIMENT_EXECUTION_ENABLED", "true"
    )
    calls = []

    async def fake_orchestrated_trial(
        units, *, task, dataset_fingerprint, context_cache, checkpoint_path
    ):
        # Sustituto SIN red: no se importa ninguna función que llame API.
        calls.append({
            "task_id": task["task_id"],
            "units": len(units),
        })
        assert dataset_fingerprint == dataset.fingerprint
        assert context_cache == worker.CONTEXT
        assert checkpoint_path == worker.CHECKPOINTS
        return {
            "task_id": task["task_id"],
            "model": task["model"],
            "repetition": task["repetition"],
            "dataset_fingerprint": dataset_fingerprint,
            "status": "success",
            "unit_results": [
                {
                    "id": unit.technical_id,
                    "status": "success",
                    "prediction": "no potencialmente abusiva",
                }
                for unit in units
            ],
            "report": {
                "total_clauses": len(units),
                "successful_clauses": len(units),
            },
            "llm_metrics": [{"cost_usd": 0.0025}],
            "execution_id": "simulated-only-no-external-calls",
            "duration_ms": 12.0,
            "errors": [],
        }

    monkeypatch.setattr(
        worker, "run_orchestrated_trial", fake_orchestrated_trial
    )

    unauthorized = CLIENT.post(
        "/experimental/jobs",
        json={"task_id": "ET01-R1", "accept_paid_execution": True},
    )
    assert unauthorized.status_code == 403
    denied = CLIENT.post(
        "/experimental/jobs",
        headers=HEADERS,
        json={"task_id": "ET01-R1", "accept_paid_execution": False},
    )
    assert denied.status_code == 400
    unknown = CLIENT.post(
        "/experimental/jobs",
        headers=HEADERS,
        json={"task_id": "ET99-R1", "accept_paid_execution": True},
    )
    assert unknown.status_code == 404

    submitted = CLIENT.post(
        "/experimental/jobs",
        headers=HEADERS,
        json={"task_id": "ET01-R1", "accept_paid_execution": True},
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["status"] == "queued"

    job_path = folder / "binary_jobs" / "ET01-R1.json"
    assert json.loads(
        job_path.read_text(encoding="utf-8")
    )["status"] == "queued"
    duplicate = CLIENT.post(
        "/experimental/jobs",
        headers=HEADERS,
        json={"task_id": "ET01-R1", "accept_paid_execution": True},
    )
    assert duplicate.status_code == 409

    worker.execute_job(job_path)
    job = json.loads(job_path.read_text(encoding="utf-8"))
    assert job["status"] == "completed"
    assert job["execution_id"] == "simulated-only-no-external-calls"
    assert calls == [{"task_id": "ET01-R1", "units": 21}]

    overview = CLIENT.get(
        "/experimental/overview", headers=HEADERS
    ).json()
    assert overview["progress"]["counts"] == {
        "completed": 1, "failed": 0, "pending": 89,
    }
    assert overview["jobs"][0]["status"] == "completed"
    assert overview["progress"]["reported_cost_usd"] == 0.0025

    metrics = CLIENT.get(
        "/experimental/results", headers=HEADERS
    )
    assert metrics.status_code == 200, metrics.text
    assert metrics.json()["results_are_final"] is False
    first = metrics.json()["documents"][0]
    assert first["task_id"] == "ET01-R1"
    assert first["status"] == "completed"
    assert first["predictions_valid"] == 21
    assert first["quality_is_final_for_document"] is True

    repeated = CLIENT.post(
        "/experimental/jobs",
        headers=HEADERS,
        json={"task_id": "ET01-R1", "accept_paid_execution": True},
    )
    assert repeated.status_code == 409


def test_worker_rejects_wrong_dataset_fingerprint(
    isolated_environment, monkeypatch,
):
    folder, dataset = isolated_environment
    calls = []

    async def forbidden_run(*_args, **_kwargs):
        calls.append("model_called")
        raise AssertionError("No se debe ejecutar el modelo.")

    monkeypatch.setattr(
        worker, "run_orchestrated_trial", forbidden_run
    )
    path = folder / "invalid-task.json"
    path.write_text(
        json.dumps({
            "task_id": "ET01-R1",
            "dataset_fingerprint": "0" * 64,
            "status": "queued",
        }),
        encoding="utf-8",
    )
    worker.execute_job(path)
    result = json.loads(path.read_text(encoding="utf-8"))
    assert result["status"] == "invalid"
    assert calls == []
    assert not worker.RESULTS.exists()



def test_checkpoint_progress_ignores_other_models_and_labels(
    isolated_environment,
):
    """La API solo muestra contadores del tratamiento V2 correspondiente."""
    folder, dataset = isolated_environment
    task = make_experimental_plan(dataset)["tasks"][0]
    path = folder / "v2_binary_unit_checkpoints.jsonl"
    base = {
        "task_id": task["task_id"],
        "model": task["model"],
        "repetition": task["repetition"],
        "dataset_fingerprint": dataset.fingerprint,
        "text_sha256": "a" * 64,
    }
    records = [
        {
            **base,
            "id": "ToS01-U001",
            "status": "success",
            "response": {"status": "success"},
        },
        {
            **base,
            "id": "ToS01-U002",
            "status": "error",
            "response": {"status": "error"},
        },
        # Debe ignorarse: proviene de otro modelo.
        {
            **base,
            "model": "modelo-ajeno",
            "id": "ToS01-U003",
            "status": "success",
            "response": {"status": "success"},
        },
        # Debe ignorarse: huella de otro dataset.
        {
            **base,
            "dataset_fingerprint": "f" * 64,
            "id": "ToS01-U004",
            "status": "success",
            "response": {"status": "success"},
        },
        # Debe ignorarse: misma tarea pero fragmento de otro documento.
        {
            **base,
            "id": "ToS02-U001",
            "status": "success",
            "response": {"status": "success"},
        },
    ]
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False) + "\n"
            for row in records
        ),
        encoding="utf-8",
    )

    response = CLIENT.get(
        "/experimental/overview", headers=HEADERS
    )
    assert response.status_code == 200
    data = response.json()
    selected = data["tasks"][0]
    assert selected["task_id"] == "ET01-R1"
    assert selected["unit_progress"] == {
        "total": 21,
        "checkpoint_successful": 1,
        "checkpoint_failed": 1,
        "remaining": 20,
    }
    # Los checkpoints no equivalen a tareas documentales completas.
    assert data["progress"]["counts"] == {
        "completed": 0, "failed": 0, "pending": 90,
    }
    assert data["tasks"][1]["unit_progress"][
        "checkpoint_successful"
    ] == 0
    # Los resultados de referencia no se exponen por el endpoint de control.
    assert "original_text" not in response.text
    assert "label" not in selected["unit_progress"]
    assert "classification_labels" in data["manifest"]
