"""Evaluación independiente POR DOCUMENTO de las tareas de campaña.

Evita interpretar cobertura global baja como mala exactitud del modelo.
Las métricas de calidad documental son definitivas solo si el documento
está COMPLETO; los errores operativos no son etiquetas negativas.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.evaluation.campaign import (
    completed_document_run, document_units, sum_reported_cost,
)
from app.evaluation.design import make_experimental_plan
from app.evaluation.groundtruth import GroundTruth
from app.evaluation.binary_groundtruth import BINARY_LABELS as LABELS
from app.evaluation.binary_scoring import _score_subset
from app.evaluation.repetition_metrics import (
    _select_best_attempt, _unit_predictions,
)


def score_campaign_documents(
    groundtruth: GroundTruth,
    records: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Una fila por cada tarea ET01-R1..ET30-R3; 90 filas en total.

    Los resultados no ejecutados tienen métricas None, nunca 0%.
    Los resultados incompletos distinguen calidad provisional sobre
    predicciones presentes y fallos observados de unidades sin ejecutar.
    """
    plan = make_experimental_plan(groundtruth)
    tasks = plan["tasks"]
    by_task = {task["task_id"]: task for task in tasks}
    for row in records:
        task_id = row.get("task_id")
        if task_id not in by_task:
            raise ValueError(f"Tarea no prevista en el diseño: {task_id}")
        task = by_task[task_id]
        if (
            row.get("dataset_fingerprint") != groundtruth.fingerprint
            or row.get("model") != task["model"]
            or row.get("repetition") != task["repetition"]
        ):
            raise ValueError(f"Registro incompatible para la tarea {task_id}")

    detail: list[dict[str, Any]] = []
    for task in tasks:
        units = document_units(groundtruth, task)
        expected_ids = [unit.technical_id for unit in units]
        attempts = [
            row for row in records
            if row.get("task_id") == task["task_id"]
        ]
        selected = _select_best_attempt(
            records, task,
            expected_ids=expected_ids,
            fingerprint=groundtruth.fingerprint,
        )
        completed = selected is not None and completed_document_run(
            selected, task, expected_ids, groundtruth.fingerprint,
        )
        prediction_map = _unit_predictions(
            selected, expected_ids=set(expected_ids)
        )
        evaluated_units = [
            unit for unit in units
            if unit.technical_id in prediction_map
        ]
        observed_scores = (
            _score_subset(evaluated_units, prediction_map, LABELS)
            if evaluated_units else None
        )
        observed_eligible = [
            unit for unit in evaluated_units
            if unit.applicability == "Evaluable"
        ]
        eligible_scores = (
            _score_subset(observed_eligible, prediction_map, LABELS[1:])
            if observed_eligible else None
        )

        result_entries = (
            selected.get("unit_results", []) if selected else []
        )
        if not isinstance(result_entries, list):
            result_entries = []
        explicit_errors = sum(
            item.get("status") == "error"
            for item in result_entries
            if isinstance(item, dict)
        )
        status = (
            "completed" if completed
            else "not_executed" if selected is None
            else "incomplete"
        )

        detail.append({
            "task_id": task["task_id"],
            "document_id": task["document_id"],
            "platform": task["platform"],
            "treatment": task["treatment"],
            "model": task["model"],
            "repetition": task["repetition"],
            "status": status,
            "unit_count": len(units),
            "predictions_valid": len(prediction_map),
            "predictions_missing": len(units) - len(prediction_map),
            "explicit_unit_errors": explicit_errors,
            "attempt_records": len(attempts),
            "correct_on_observed": (
                observed_scores["correct"] if observed_scores else None
            ),
            "accuracy_on_observed": (
                observed_scores["accuracy"] if observed_scores else None
            ),
            "f1_macro_on_observed": (
                observed_scores["f1_macro"] if observed_scores else None
            ),
            "accuracy_evaluable_observed": (
                eligible_scores["accuracy"] if eligible_scores else None
            ),
            "f1_macro_evaluable_observed": (
                eligible_scores["f1_macro"] if eligible_scores else None
            ),
            "quality_is_final_for_document": bool(completed),
            "confusion_matrix_on_observed": (
                observed_scores["confusion_matrix"] if observed_scores else None
            ),
            "duration_ms_reported": round(sum(
                float(row["duration_ms"])
                for row in attempts
                if isinstance(row.get("duration_ms"), (int, float))
                and float(row["duration_ms"]) >= 0
            ), 3),
            "cost_usd_reported": round(
                sum(sum_reported_cost(row) for row in attempts), 8
            ),
            "cost_reporting_incomplete_attempts": sum(
                bool(row.get("reported_cost_incomplete", False))
                for row in attempts
            ),
        })
    return detail
