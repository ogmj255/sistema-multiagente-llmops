"""Métricas de calidad por tratamiento y repetición, separadas de inferencia.

No modifica el ground truth ni lo envía a LLM/RAG. Los resultados incompletos
se muestran con denominador fijo y cobertura, sin fingir 547 aciertos/fallos.
"""

from __future__ import annotations

from collections import Counter
from math import sqrt
from typing import Any, Mapping, Sequence

from app.evaluation.campaign import (
    completed_document_run,
    document_units,
    sum_reported_cost,
)
from app.evaluation.design import MODELS, REPETITIONS, make_experimental_plan
from app.evaluation.groundtruth import GroundTruth
from app.evaluation.binary_groundtruth import BINARY_LABELS as LABELS
from app.evaluation.binary_scoring import _score_subset

VALID = set(LABELS)


def _select_best_attempt(
    records: Sequence[dict[str, Any]],
    task: Mapping[str, Any],
    *,
    expected_ids: list[str],
    fingerprint: str,
) -> dict[str, Any] | None:
    """Prefiere la última tarea completada; si no existe, la más reciente."""
    attempts = [
        row for row in records
        if row.get("task_id") == task["task_id"]
        and row.get("dataset_fingerprint") == fingerprint
    ]
    for row in reversed(attempts):
        if completed_document_run(row, task, expected_ids, fingerprint):
            return row
    return attempts[-1] if attempts else None


def _unit_predictions(
    row: Mapping[str, Any] | None,
    *,
    expected_ids: set[str],
) -> dict[str, str]:
    """Extrae solamente categorías válidas, sin duplicados ni IDs ajenos."""
    predictions: dict[str, str] = {}
    if row is None:
        return predictions
    raw = row.get("unit_results")
    if not isinstance(raw, list):
        return predictions

    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        technical_id = item.get("id")
        if not isinstance(technical_id, str):
            continue
        if technical_id not in expected_ids:
            raise ValueError(
                f"Predicción para unidad ajena al documento: {technical_id}"
            )
        if technical_id in seen:
            raise ValueError(
                f"Predicción duplicada para unidad: {technical_id}"
            )
        seen.add(technical_id)
        label = item.get("prediction")
        if (
            item.get("status") == "success"
            and isinstance(label, str)
            and label in VALID
        ):
            predictions[technical_id] = label
    return predictions


def score_campaign_repetitions(
    groundtruth: GroundTruth,
    records: Sequence[dict[str, Any]],
) -> dict[str, object]:
    """Puntúa 3 modelos × 3 repeticiones; 547 unidades por celda.

    Incluye las cuatro clases (N/A) y tres clases evaluables. Los errores
    reducen la cobertura y se cuantifican de modo independiente.
    """
    plan = make_experimental_plan(groundtruth)
    tasks = plan["tasks"]
    task_by_treatment_rep: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for task in tasks:
        task_by_treatment_rep.setdefault(
            (task["treatment"], task["repetition"]), []
        ).append(task)

    # No mezclar datasets ni modelos: los intentos deben corresponder
    # a un ID de tarea definido, aun si son errores experimentales.
    indexed_tasks = {task["task_id"]: task for task in tasks}
    for row in records:
        task_id = row.get("task_id")
        if task_id not in indexed_tasks:
            raise ValueError(f"Registro de tarea no incluida en el plan: {task_id}")
        task = indexed_tasks[task_id]
        if (
            row.get("dataset_fingerprint") != groundtruth.fingerprint
            or row.get("model") != task["model"]
            or row.get("repetition") != task["repetition"]
        ):
            raise ValueError(
                f"Registro incompatible con el diseño: {task_id}"
            )

    detail: list[dict[str, object]] = []
    for treatment, model in MODELS:
        for repetition in range(1, REPETITIONS + 1):
            relevant_tasks = task_by_treatment_rep[
                treatment, repetition
            ]
            predicted: dict[str, str] = {}
            document_counts = Counter()
            duration_ms = 0.0
            total_cost = 0.0
            unknown_cost_attempts = 0
            attempt_count = 0
            pending_document_units = 0
            unavailable_in_started_documents = 0
            explicit_unit_errors = 0

            for task in relevant_tasks:
                units = document_units(groundtruth, task)
                expected_ids = [unit.technical_id for unit in units]
                task_attempts = [
                    row for row in records
                    if row.get("task_id") == task["task_id"]
                ]
                attempt_count += len(task_attempts)
                for row in task_attempts:
                    duration = row.get("duration_ms")
                    if isinstance(duration, (int, float)) and duration >= 0:
                        duration_ms += duration
                    total_cost += sum_reported_cost(row)
                    unknown_cost_attempts += int(
                        row.get("reported_cost_incomplete", False)
                    )

                selected = _select_best_attempt(
                    records, task,
                    expected_ids=expected_ids,
                    fingerprint=groundtruth.fingerprint,
                )
                if selected is None:
                    document_counts["pending"] += 1
                    pending_document_units += len(units)
                elif completed_document_run(
                    selected, task, expected_ids, groundtruth.fingerprint
                ):
                    document_counts["completed"] += 1
                else:
                    document_counts["incomplete"] += 1

                extracted = _unit_predictions(
                    selected, expected_ids=set(expected_ids)
                )
                if selected is not None:
                    unavailable_in_started_documents += (
                        len(units) - len(extracted)
                    )
                    unit_results = selected.get("unit_results", [])
                    if isinstance(unit_results, list):
                        explicit_unit_errors += sum(
                            result.get("status") == "error"
                            for result in unit_results
                            if isinstance(result, dict)
                        )
                for technical_id, label in extracted.items():
                    if technical_id in predicted:
                        raise ValueError(
                            f"Unidad duplicada entre ToS: {technical_id}"
                        )
                    predicted[technical_id] = label

            total = len(groundtruth.units)
            covered = len(predicted)
            all_scores = _score_subset(
                groundtruth.units, predicted, LABELS
            )
            eligible_scores = _score_subset(
                (unit for unit in groundtruth.units
                 if unit.applicability == "Evaluable"),
                predicted, LABELS[1:],
            )

            detail.append({
                "treatment": treatment,
                "model": model,
                "repetition": repetition,
                "documents_completed": document_counts["completed"],
                "documents_incomplete": document_counts["incomplete"],
                "documents_pending": document_counts["pending"],
                "prediction_attempt_records": attempt_count,
                "total_units": total,
                "predictions_valid": covered,
                "missing_or_invalid": total - covered,
                # No llamar 'tasa de error' a unidades no ejecutadas.
                "unavailable_prediction_rate": round(
                    (total - covered) / total, 6
                ),
                "pending_document_units": pending_document_units,
                "unavailable_in_started_documents": (
                    unavailable_in_started_documents
                ),
                "explicit_unit_errors": explicit_unit_errors,
                "all_units": all_scores,
                "evaluable_units": eligible_scores,
                "duration_ms_reported": round(duration_ms, 3),
                "cost_usd_reported": round(total_cost, 8),
                "cost_reporting_incomplete_attempts": unknown_cost_attempts,
                "is_complete": (
                    document_counts["completed"] == 10
                    and covered == total
                ),
            })

    aggregate: list[dict[str, object]] = []
    for treatment, model in MODELS:
        runs = [row for row in detail if row["treatment"] == treatment]
        if len(runs) == REPETITIONS and all(row["is_complete"] for row in runs):
            measures = [
                float(row["evaluable_units"]["f1_macro"])
                for row in runs
            ]
            mean = sum(measures) / len(measures)
            sample_sd = sqrt(
                sum((x - mean) ** 2 for x in measures)
                / (len(measures) - 1)
            )
            aggregate.append({
                "treatment": treatment,
                "model": model,
                "complete_repetitions": REPETITIONS,
                "f1_macro_mean": round(mean, 6),
                "f1_macro_sample_sd": round(sample_sd, 6),
            })
        else:
            aggregate.append({
                "treatment": treatment,
                "model": model,
                "complete_repetitions": sum(row["is_complete"] for row in runs),
                "f1_macro_mean": None,
                "f1_macro_sample_sd": None,
            })

    return {
        "dataset_fingerprint": groundtruth.fingerprint,
        "design_executions": plan["executions"],
        "design_predictions": plan["expected_unit_predictions"],
        "results_are_final": all(row["is_complete"] for row in detail),
        "by_treatment_repetition": detail,
        "model_aggregate": aggregate,
        "notes": (
            "En el protocolo V2, el F1 principal corresponde solo a NPA/PA "
            "sobre unidades evaluables. Las métricas globales de estados "
            "incluyen no aplicable únicamente como diagnóstico. "
            "Las métricas globales sobre 547 fragmentos se deben "
            "interpretar junto con la cobertura. La tasa de predicciones "
            "no disponibles NO es una tasa de error operativo: distingue "
            "unidades pendientes y errores explícitos. La calidad del "
            "documento procesado aparece en formal_metrics_by_document; "
            "no pueden contrastarse hipótesis mientras falten tareas. "
            "Los costos pueden ser subestimaciones si falló la captura."
        ),
    }
