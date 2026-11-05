"""Métricas de clasificación que contabilizan también los fallos."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Iterable

from app.evaluation.groundtruth import GroundTruth, GroundTruthUnit, LABELS

INVALID = "__invalid__"


def read_predictions(path: str | Path) -> list[dict[str, object]]:
    """Lee predicciones JSONL ya ejecutadas; nunca invoca modelos."""
    records: list[dict[str, object]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"JSONL inválido en la línea {number}."
                ) from error
            if not isinstance(record, dict):
                raise ValueError(
                    f"Se esperaba un objeto JSON en la línea {number}."
                )
            records.append(record)
    return records


def _score_subset(
    units: Iterable[GroundTruthUnit],
    predictions: dict[str, str],
    classes: tuple[str, ...],
) -> dict[str, object]:
    subset = tuple(units)
    actual_counts = Counter(unit.label for unit in subset)
    matrix = {
        label: {candidate: 0 for candidate in (*LABELS, INVALID)}
        for label in classes
    }
    correct = 0
    covered = 0

    for unit in subset:
        predicted = predictions.get(unit.technical_id, INVALID)
        if predicted not in LABELS:
            predicted = INVALID
        matrix[unit.label][predicted] += 1
        correct += int(predicted == unit.label)
        covered += int(predicted != INVALID)

    per_class: dict[str, dict[str, float | int]] = {}
    for label in classes:
        tp = matrix[label][label]
        fp = sum(
            matrix[other][label] for other in classes if other != label
        )
        fn = actual_counts[label] - tp
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision + recall
            else 0.0
        )
        per_class[label] = {
            "support": actual_counts[label],
            "precision": round(precision, 6),
            "recall": round(recall, 6),
            "f1": round(f1, 6),
        }

    size = len(subset)
    return {
        "total": size,
        "predictions_valid": covered,
        "missing_or_invalid": size - covered,
        "correct": correct,
        "coverage": round(covered / size, 6) if size else 0.0,
        "accuracy": round(correct / size, 6) if size else 0.0,
        "f1_macro": round(
            sum(per_class[label]["f1"] for label in classes) / len(classes),
            6,
        ),
        "f1_weighted": round(
            sum(
                per_class[label]["f1"] * actual_counts[label]
                for label in classes
            ) / size,
            6,
        ) if size else 0.0,
        "per_class": per_class,
        "confusion_matrix": matrix,
    }


def score_predictions(
    groundtruth: GroundTruth,
    records: Iterable[dict[str, object]],
    *,
    model: str,
) -> dict[str, object]:
    """Evalúa un modelo con matriz de confusión y denominador fijo."""
    ids = {unit.technical_id for unit in groundtruth.units}
    selected: dict[str, str] = {}
    attempts = 0

    for record in records:
        if record.get("model") != model:
            continue
        attempts += 1
        if record.get("dataset_fingerprint") != groundtruth.fingerprint:
            raise ValueError(
                "La predicción no corresponde a esta versión del ground truth."
            )
        technical_id = record.get("id")
        if not isinstance(technical_id, str) or technical_id not in ids:
            raise ValueError(
                f"ID de predicción desconocido: {technical_id!r}."
            )
        predicted = record.get("prediction")
        selected[technical_id] = (
            predicted
            if record.get("status") == "success" and predicted in LABELS
            else INVALID
        )

    if attempts == 0:
        raise ValueError(f"No se encontraron predicciones para {model!r}.")

    evaluated = _score_subset(groundtruth.units, selected, LABELS)
    eligible = _score_subset(
        (
            unit for unit in groundtruth.units
            if unit.applicability == "Evaluable"
        ),
        selected,
        LABELS[1:],
    )
    return {
        "model": model,
        "dataset_fingerprint": groundtruth.fingerprint,
        "attempt_records": attempts,
        "latest_unit_records": len(selected),
        "all_units": evaluated,
        "evaluable_units": eligible,
    }
