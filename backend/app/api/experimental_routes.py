"""API experimental interna (V2): planificación y cola autorizada.

No ejecuta inferencias dentro del proceso FastAPI. El worker separado
recoge tareas validadas de disco, con checkpoint y auditoría.
"""

from __future__ import annotations

import hmac
import json
import os
import re
import time
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.evaluation.binary_groundtruth import (
    binary_manifest, load_binary_groundtruth_v2,
)
from app.evaluation.campaign import (
    completed_document_run, document_units, run_classification,
    sum_reported_cost, task_progress,
)
from app.evaluation.design import make_experimental_plan
from app.evaluation.pilot import read_jsonl

router = APIRouter(prefix="/experimental", tags=["Evaluación experimental V2"])
DATA_DIR = Path(os.getenv("EXPERIMENT_DATA_DIR", "/app/data/evaluation"))
TASK_PATTERN = re.compile(r"ET\d{2}-R[1-3]\Z")


def require_operator(
    token: Annotated[str | None, Header(alias="X-Experiment-Token")] = None,
    operator_password: Annotated[str | None, Header(alias="X-Experiment-Operator")] = None,
) -> None:
    configured = os.getenv("EXPERIMENT_ADMIN_TOKEN", "").strip()
    expected_password = os.getenv("EXPERIMENT_OPERATOR_PASSWORD", "").strip()
    if (
        not configured
        or not expected_password
        or token is None
        or operator_password is None
        or not hmac.compare_digest(token, configured)
        or not hmac.compare_digest(operator_password, expected_password)
    ):
        raise HTTPException(status_code=403, detail="Acceso experimental no autorizado.")


def _load():
    csv_path = DATA_DIR / "ground_truth_547.csv"
    if not csv_path.exists():
        raise HTTPException(
            status_code=503,
            detail="Corpus congelado no montado en el backend.",
        )
    data = load_binary_groundtruth_v2(csv_path)
    return data, make_experimental_plan(data)


def _runs():
    return read_jsonl(DATA_DIR / "v2_binary_campaign_runs.jsonl")


def _preflight_registered(dataset_fingerprint: str) -> bool:
    """Presencia del manifiesto; el worker revalida Chroma/Ollama al ejecutar."""
    path = DATA_DIR / "v2_binary_preflight_manifest.json"
    if not path.is_file():
        return False
    try:
        frozen = json.loads(path.read_text(encoding="utf-8"))
        return (
            isinstance(frozen, dict)
            and frozen.get("environment", {}).get("dataset_fingerprint")
            == dataset_fingerprint
        )
    except (OSError, ValueError, AttributeError, TypeError):
        return False


def _worker_online() -> bool:
    """Latido reciente; no asumir que un proceso de cobro está activo."""
    heartbeat = DATA_DIR / "v2_binary_worker_heartbeat.json"
    if not heartbeat.exists():
        return False
    try:
        details = json.loads(heartbeat.read_text(encoding="utf-8"))
        timestamp = float(details.get("timestamp", 0))
        return (
            details.get("protocol") == "NPA-PA-v2.0"
            and 0 <= time.time() - timestamp <= 15
        )
    except (OSError, ValueError, TypeError):
        return False



def _job_files():
    folder = DATA_DIR / "binary_jobs"
    if not folder.exists():
        return []
    jobs = []
    for path in folder.glob("*.json"):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(row, dict):
                jobs.append(row)
        except (OSError, ValueError):
            continue
    return sorted(jobs, key=lambda x: x.get("queued_at", ""), reverse=True)


def _unit_checkpoint_progress(groundtruth, tasks: list[dict]) -> dict:
    """Progreso observado por tarea, aislado por dataset y modelo.

    Lee únicamente checkpoints V2 y nunca expone textos originales,
    etiquetas humanas, prompts ni claves al frontend.
    """
    task_index = {task["task_id"]: task for task in tasks}
    texts = {unit.technical_id: unit.text_sha256 for unit in groundtruth.units}
    successful = {task_id: set() for task_id in task_index}
    failed = {task_id: set() for task_id in task_index}

    for row in read_jsonl(DATA_DIR / "v2_binary_unit_checkpoints.jsonl"):
        if not isinstance(row, dict):
            continue
        task_id = row.get("task_id")
        task = task_index.get(task_id)
        if task is None:
            continue
        unit_id = row.get("id")
        if (
            not isinstance(unit_id, str)
            or not unit_id.startswith(task["document_id"] + "-U")
            or row.get("dataset_fingerprint") != groundtruth.fingerprint
            or row.get("model") != task["model"]
            or row.get("repetition") != task["repetition"]
            or row.get("text_sha256") != texts.get(unit_id)
        ):
            continue
        if (
            row.get("status") == "success"
            and isinstance(row.get("response"), dict)
            and row["response"].get("status") == "success"
        ):
            successful[task_id].add(unit_id)
        elif row.get("status") == "error":
            failed[task_id].add(unit_id)

    return {
        task_id: {
            "total": task["unit_count"],
            "checkpoint_successful": len(successful[task_id]),
            "checkpoint_failed": len(failed[task_id] - successful[task_id]),
            "remaining": task["unit_count"] - len(successful[task_id]),
        }
        for task_id, task in task_index.items()
    }


@router.get("/overview")
def experimental_overview() -> dict:
    groundtruth, plan = _load()
    tasks = plan["tasks"]
    records = _runs()
    jobs = _job_files()
    job_by_task = {
        job["task_id"]: job
        for job in reversed(jobs)
        if isinstance(job.get("task_id"), str)
    }
    unit_progress = _unit_checkpoint_progress(groundtruth, tasks)
    by_task = {}
    for task in tasks:
        ids = [
            unit.technical_id
            for unit in document_units(groundtruth, task)
        ]
        by_task[task["task_id"]] = run_classification(
            records, task, ids, groundtruth.fingerprint
        )
    return {
        "protocol": "NPA-PA-v2.0",
        "manifest": binary_manifest(groundtruth),
        "progress": task_progress(groundtruth, tasks, records),
        "execution_enabled": os.getenv(
            "EXPERIMENT_EXECUTION_ENABLED", "false"
        ).lower() == "true",
        "worker_online": _worker_online(),
        "preflight_registered": _preflight_registered(groundtruth.fingerprint),
        "tasks": [
            {
                **task,
                "status": by_task[task["task_id"]],
                "job_status": job_by_task.get(task["task_id"], {}).get("status"),
                "unit_progress": unit_progress[task["task_id"]],
            }
            for task in tasks
        ],
        "jobs": jobs[:30],
        "risk_note": (
            "El costo de una tarea es variable; no existe límite duro "
            "de facturación. Las etiquetas humanas no se envían al LLM."
        ),
    }


class TaskOrder(BaseModel):
    task_id: str = Field(pattern=r"^ET\d{2}-R[1-3]$")
    accept_paid_execution: bool


@router.post("/jobs", dependencies=[Depends(require_operator)])
def enqueue_experiment(request: TaskOrder) -> dict[str, str]:
    if os.getenv(
        "EXPERIMENT_EXECUTION_ENABLED", "false"
    ).lower() != "true":
        raise HTTPException(
            status_code=403,
            detail="Ejecución deshabilitada por configuración.",
        )
    if not request.accept_paid_execution:
        raise HTTPException(
            status_code=400,
            detail="Debe autorizar explícitamente el consumo de créditos.",
        )
    if not _worker_online():
        raise HTTPException(
            status_code=503,
            detail="Worker experimental no disponible. No se encoló ninguna tarea.",
        )
    data, plan = _load()
    if not _preflight_registered(data.fingerprint):
        raise HTTPException(
            status_code=409,
            detail="Falta manifiesto preflight V2 para la referencia vigente.",
        )
    task = next(
        (t for t in plan["tasks"] if t["task_id"] == request.task_id),
        None,
    )
    if task is None:
        raise HTTPException(status_code=404, detail="Tarea no definida.")
    ids = [unit.technical_id for unit in document_units(data, task)]
    if run_classification(
        _runs(), task, ids, data.fingerprint
    ) == "completed":
        raise HTTPException(
            status_code=409, detail="Tarea ya completada en protocolo V2.",
        )

    # Cola sencilla, idempotente y de un único trabajador.
    folder = DATA_DIR / "binary_jobs"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{request.task_id}.json"
    if path.exists():
        row = json.loads(path.read_text(encoding="utf-8"))
        if row.get("status") in {"queued", "running", "completed"}:
            raise HTTPException(
                status_code=409, detail="La tarea ya figura en la cola.",
            )

    from datetime import UTC, datetime
    payload = {
        "task_id": task["task_id"],
        "document_id": task["document_id"],
        "model": task["model"],
        "repetition": task["repetition"],
        "protocol": "NPA-PA-v2.0",
        "dataset_fingerprint": data.fingerprint,
        "status": "queued",
        "queued_at": datetime.now(UTC).isoformat(),
    }
    # Escritura atómica: reemplaza un fallo histórico pero nunca un
    # trabajo activo. La prueba de concurrencia reside en el worker.
    temp = folder / f".{request.task_id}.{os.getpid()}.tmp"
    temp.write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8",
    )
    os.replace(temp, path)
    return {
        "task_id": request.task_id,
        "status": "queued",
        "message": "La tarea será procesada por el worker experimental.",
    }


@router.get("/results")
def experimental_results() -> dict:
    """Resúmenes y métricas SOLO para el investigador.

    Las etiquetas humanas se usan aquí para puntuación, después de
    las inferencias; jamás pasan a la entrada del agente jurídico.
    """
    from app.evaluation.document_metrics import score_campaign_documents
    from app.evaluation.repetition_metrics import score_campaign_repetitions

    dataset, _plan = _load()
    records = _runs()
    documents = score_campaign_documents(dataset, records)
    repetitions = score_campaign_repetitions(dataset, records)
    return {
        "protocol": "NPA-PA-v2.0",
        "documents": documents,
        "repetitions": repetitions["by_treatment_repetition"],
        "model_aggregate": repetitions["model_aggregate"],
        "results_are_final": repetitions["results_are_final"],
        "caution": (
            "La exactitud binaria se calcula sobre unidades evaluables. "
            "No deben confundirse documentos pendientes con errores "
            "operativos ni utilizar métricas de cobertura global como "
            "exactitud de un documento completado."
        ),
    }

@router.get("/tasks/{task_id}/units")
def experimental_task_units(task_id: str) -> dict:
    """Seguimiento por ID técnico; sin texto, etiquetas ni predicciones."""
    dataset, plan = _load()
    task = next(
        (item for item in plan["tasks"] if item["task_id"] == task_id),
        None,
    )
    if task is None:
        raise HTTPException(status_code=404, detail="Tarea desconocida.")
    units = document_units(dataset, task)
    statuses = {unit.technical_id: "pending" for unit in units}
    hashes = {unit.technical_id: unit.text_sha256 for unit in units}
    for row in read_jsonl(DATA_DIR / "v2_binary_unit_checkpoints.jsonl"):
        unit_id = row.get("id")
        if (
            row.get("task_id") != task_id
            or unit_id not in statuses
            or row.get("model") != task["model"]
            or row.get("repetition") != task["repetition"]
            or row.get("dataset_fingerprint") != dataset.fingerprint
            or row.get("text_sha256") != hashes.get(unit_id)
        ):
            continue
        if (
            row.get("status") == "success"
            and isinstance(row.get("response"), dict)
            and row["response"].get("status") == "success"
        ):
            statuses[unit_id] = "completed"
        elif row.get("status") == "error" and statuses[unit_id] != "completed":
            statuses[unit_id] = "failed"

    return {
        "task_id": task_id,
        "document_id": task["document_id"],
        "model": task["model"],
        "repetition": task["repetition"],
        "units": [
            {"id": unit.technical_id, "status": statuses[unit.technical_id]}
            for unit in units
        ],
        "note": "Estados derivados exclusivamente de checkpoints V2.",
    }



@router.get("/tasks/{task_id}/predictions")
def experimental_task_predictions(task_id: str) -> dict:
    """Predicciones V2 auditables sin revelar la etiqueta humana.

    Solo devuelve un resultado documental completo de la tarea/modelo/
    repetición solicitados; no mezcla intentos ni versiones de corpus.
    """
    dataset, plan = _load()
    task = next(
        (row for row in plan["tasks"] if row["task_id"] == task_id),
        None,
    )
    if task is None:
        raise HTTPException(status_code=404, detail="Tarea desconocida.")

    units = document_units(dataset, task)
    ids = [unit.technical_id for unit in units]
    for row in reversed(_runs()):
        if not completed_document_run(row, task, ids, dataset.fingerprint):
            continue
        by_id = {
            item["id"]: item
            for item in row["unit_results"]
        }
        return {
            "task_id": task_id,
            "protocol": "NPA-PA-v2.0",
            "model": task["model"],
            "repetition": task["repetition"],
            "status": "completed",
            "execution_id": row.get("execution_id"),
            "duration_ms": row.get("duration_ms"),
            "cost_usd_reported": sum_reported_cost(row),
            "predictions": [
                {
                    "unit_id": unit_id,
                    "status": by_id[unit_id]["status"],
                    "prediction": by_id[unit_id]["prediction"],
                }
                for unit_id in ids
            ],
            "note": "Predicciones del modelo; no incluye etiquetas del ground truth.",
        }
    return {
        "task_id": task_id,
        "protocol": "NPA-PA-v2.0",
        "status": "not_completed",
        "predictions": [],
        "note": "Aún no existe un resultado documental V2 completo.",
    }
