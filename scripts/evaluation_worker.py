"""Worker V2 aislado: ejecuta tareas autorizadas con LangGraph+MCP.

Se lanza desde Docker Compose, nunca dentro de la sesión Streamlit o del
proceso de FastAPI. Procesa en serie y respeta checkpoints por unidad.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from threading import Event, Thread
from datetime import UTC, datetime
from pathlib import Path

from app.evaluation.binary_groundtruth import load_binary_groundtruth_v2
from app.evaluation.campaign import (
    document_units, run_classification,
)
from app.evaluation.design import make_experimental_plan
from app.evaluation.orchestrated import run_orchestrated_trial
from app.evaluation.pilot import append_jsonl, read_jsonl

DIRECTORY = Path(os.getenv("EXPERIMENT_DATA_DIR", "/app/data/evaluation"))
QUEUE = DIRECTORY / "binary_jobs"
RESULTS = DIRECTORY / "v2_binary_campaign_runs.jsonl"
CONTEXT = DIRECTORY / "v2_binary_legal_context_snapshots.jsonl"
CHECKPOINTS = DIRECTORY / "v2_binary_unit_checkpoints.jsonl"

HEARTBEAT = DIRECTORY / "v2_binary_worker_heartbeat.json"


def _write_heartbeat() -> None:
    """Indicador de vida para no encolar gastos si no existe worker."""
    HEARTBEAT.parent.mkdir(parents=True, exist_ok=True)
    temporary = HEARTBEAT.with_suffix(".tmp")
    temporary.write_text(
        json.dumps({
            "timestamp": time.time(),
            "protocol": "NPA-PA-v2.0",
        }), encoding="utf-8",
    )
    os.replace(temporary, HEARTBEAT)


def _heartbeat_loop(stop: Event) -> None:
    while not stop.is_set():
        _write_heartbeat()
        stop.wait(3.0)



def save_job(path: Path, job: dict) -> None:
    tmp = path.with_name(path.name + ".writing")
    tmp.write_text(
        json.dumps(job, ensure_ascii=False), encoding="utf-8",
    )
    os.replace(tmp, path)


def execute_job(path: Path) -> None:
    job = json.loads(path.read_text(encoding="utf-8"))
    if job.get("status") not in {"queued", "running"}:
        return
    data = load_binary_groundtruth_v2(DIRECTORY / "ground_truth_547.csv")
    tasks = make_experimental_plan(data)["tasks"]
    task = next(
        (row for row in tasks if row["task_id"] == job["task_id"]),
        None,
    )
    if task is None or job.get("dataset_fingerprint") != data.fingerprint:
        job["status"] = "invalid"
        job["error"] = "Tarea/huella no corresponde al protocolo V2."
        save_job(path, job)
        return

    units = document_units(data, task)
    expected_ids = [u.technical_id for u in units]
    if run_classification(
        read_jsonl(RESULTS), task, expected_ids, data.fingerprint
    ) == "completed":
        job["status"] = "completed"
        save_job(path, job)
        return

    job["status"] = "running"
    job["started_at"] = datetime.now(UTC).isoformat()
    save_job(path, job)

    try:
        result = asyncio.run(
            run_orchestrated_trial(
                units,
                task=task,
                dataset_fingerprint=data.fingerprint,
                context_cache=CONTEXT,
                checkpoint_path=CHECKPOINTS,
            )
        )
        append_jsonl(RESULTS, result)
        is_completed = run_classification(
            read_jsonl(RESULTS), task,
            expected_ids, data.fingerprint,
        ) == "completed"
        job["status"] = "completed" if is_completed else "failed"
        job["execution_id"] = result.get("execution_id")
        job["duration_ms"] = result.get("duration_ms")
        job["error_count"] = len(result.get("errors", []))
    except Exception as exc:
        # No fabricar un resultado de clasificación. La cola conserva
        # el fallo y el checkpoint de los éxitos persiste para reanudar.
        job["status"] = "failed"
        job["error"] = str(exc)[:1500]
        job["error_type"] = type(exc).__name__

    job["finished_at"] = datetime.now(UTC).isoformat()
    save_job(path, job)


def main() -> None:
    if os.getenv(
        "EXPERIMENT_EXECUTION_ENABLED", "false"
    ).lower() != "true":
        raise SystemExit("Worker experimental deshabilitado.")
    if not os.getenv("EXPERIMENT_ADMIN_TOKEN", "").strip():
        raise SystemExit("Falta EXPERIMENT_ADMIN_TOKEN.")

    QUEUE.mkdir(parents=True, exist_ok=True)
    print("Worker experimental V2 iniciado: una tarea documental por vez.", flush=True)

    stop = Event()
    heartbeat_thread = Thread(
        target=_heartbeat_loop, args=(stop,), daemon=True
    )
    heartbeat_thread.start()
    try:
        # Un único servicio/replica en Docker Compose. No escalar
        # horizontalmente sin una cola transaccional en PostgreSQL.
        while True:
            try:
                jobs = sorted(QUEUE.glob("ET*-R*.json"))
                for path in jobs:
                    job = json.loads(path.read_text(encoding="utf-8"))
                    if job.get("status") in {"queued", "running"}:
                        execute_job(path)
                        break
            except Exception as exc:
                print(
                    f"Error supervisando tareas experimentales: {exc}",
                    flush=True,
                )
            time.sleep(3)
    finally:
        stop.set()
        heartbeat_thread.join(timeout=4)
        HEARTBEAT.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
