"""Planificación y controles de reanudación de la campaña experimental.

No invoca modelos ni accede a las etiquetas humanas para generar prompts.
Las tareas ET01-R1..ET30-R3 son ejecuciones documentales independientes.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from app.evaluation.groundtruth import GroundTruth, GroundTruthUnit
from app.evaluation.binary_groundtruth import BINARY_LABELS


def document_units(
    groundtruth: GroundTruth,
    task: Mapping[str, object],
) -> tuple[GroundTruthUnit, ...]:
    document_id = str(task["document_id"])
    platform = str(task["platform"])
    items = tuple(
        unit for unit in groundtruth.units
        if unit.technical_id.startswith(document_id + "-U")
    )
    if (
        len(items) != int(task["unit_count"])
        or any(unit.platform != platform for unit in items)
    ):
        raise ValueError(
            f"{document_id}: los fragmentos no coinciden con el plan experimental."
        )
    return items


def matching_attempts(
    records: Iterable[dict[str, Any]],
    task: Mapping[str, object],
    fingerprint: str,
) -> list[dict[str, Any]]:
    """Conserva intentos previos; un error no se convierte en resultado."""
    return [
        row for row in records
        if row.get("task_id") == task["task_id"]
        and row.get("dataset_fingerprint") == fingerprint
    ]


def completed_document_run(
    row: Mapping[str, Any],
    task: Mapping[str, object],
    expected_ids: Sequence[str],
    fingerprint: str,
) -> bool:
    """Solo completa si todas las unidades del documento fueron clasificadas.

    No basta con el estado global del grafo, ni con que haya un informe.
    """
    if (
        row.get("status") != "success"
        or row.get("task_id") != task["task_id"]
        or row.get("model") != task["model"]
        or row.get("repetition") != task["repetition"]
        or row.get("dataset_fingerprint") != fingerprint
    ):
        return False

    results = row.get("unit_results")
    if not isinstance(results, list) or len(results) != len(expected_ids):
        return False
    by_id: dict[str, dict[str, Any]] = {}
    for result in results:
        if not isinstance(result, dict):
            return False
        unit_id = result.get("id")
        if not isinstance(unit_id, str) or unit_id in by_id:
            return False
        by_id[unit_id] = result

    if set(by_id) != set(expected_ids):
        return False
    if any(
        result.get("status") != "success"
        or result.get("prediction") not in BINARY_LABELS
        for result in by_id.values()
    ):
        return False

    report = row.get("report")
    if not isinstance(report, dict):
        return False
    return (
        report.get("total_clauses") == len(expected_ids)
        and report.get("successful_clauses") == len(expected_ids)
    )


def run_classification(
    records: list[dict[str, Any]],
    task: Mapping[str, object],
    expected_ids: Sequence[str],
    fingerprint: str,
) -> str:
    """Estado: completada / fallida / pendiente."""
    attempts = matching_attempts(records, task, fingerprint)
    if any(
        completed_document_run(row, task, expected_ids, fingerprint)
        for row in attempts
    ):
        return "completed"
    return "failed" if attempts else "pending"


def sum_reported_cost(row: Mapping[str, Any]) -> float:
    """Suma costos informados; los costos no reportados NO son cero."""
    metrics = row.get("llm_metrics")
    if not isinstance(metrics, list):
        return 0.0
    return sum(
        float(item["cost_usd"])
        for item in metrics
        if isinstance(item, dict)
        and isinstance(item.get("cost_usd"), (int, float))
        and not isinstance(item.get("cost_usd"), bool)
    )


def task_progress(
    groundtruth: GroundTruth,
    tasks: Sequence[dict[str, Any]],
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    """Estado global de las 90 tareas sin inferencia ni secretos."""
    counts = {"completed": 0, "failed": 0, "pending": 0}
    for task in tasks:
        ids = [unit.technical_id for unit in document_units(groundtruth, task)]
        counts[run_classification(
            records, task, ids, groundtruth.fingerprint
        )] += 1
    return {
        "dataset_fingerprint": groundtruth.fingerprint,
        "tasks": len(tasks),
        "counts": counts,
        "expected_classifications": sum(
            int(task["unit_count"]) for task in tasks
        ),
        "attempt_records": len(records),
        "reported_cost_usd": round(
            sum(sum_reported_cost(row) for row in records), 8
        ),
    }
