"""Diagnóstico de aplicabilidad y evaluación binaria NPA/PA.

NPA/PA son las únicas clases de riesgo. not_applicable es un estado
independiente; se contabiliza en matrices de diagnóstico de aplicabilidad,
pero NO como tercera clase para las métricas binarias principales.
"""

from __future__ import annotations

from collections import Counter
from typing import Iterable

from app.evaluation.binary_groundtruth import BINARY_LABELS
from app.evaluation.groundtruth import GroundTruthUnit

INVALID = "__invalid__"


def _score_subset(
    units: Iterable[GroundTruthUnit],
    predictions: dict[str, str],
    classes: tuple[str, ...],
) -> dict[str, object]:
    subset = tuple(units)
    counts = Counter(unit.label for unit in subset)
    matrix = {
        label: {candidate: 0 for candidate in (*BINARY_LABELS, INVALID)}
        for label in classes
    }
    correct = 0
    valid = 0

    for unit in subset:
        predicted = predictions.get(unit.technical_id, INVALID)
        if predicted not in BINARY_LABELS:
            predicted = INVALID
        matrix[unit.label][predicted] += 1
        correct += int(predicted == unit.label)
        valid += int(predicted != INVALID)

    per_class = {}
    for label in classes:
        tp = matrix[label][label]
        fp = sum(matrix[other][label] for other in classes if other != label)
        fn = counts[label] - tp
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = {
            "support": counts[label],
            "precision": round(precision, 6),
            "recall": round(recall, 6),
            "f1": round(f1, 6),
        }

    total = len(subset)
    return {
        "total": total,
        "predictions_valid": valid,
        "missing_or_invalid": total - valid,
        "correct": correct,
        "coverage": round(valid / total, 6) if total else 0.0,
        "accuracy": round(correct / total, 6) if total else 0.0,
        "f1_macro": round(
            sum(per_class[c]["f1"] for c in classes) / len(classes),
            6,
        ),
        "f1_weighted": round(
            sum(per_class[c]["f1"] * counts[c] for c in classes) / total,
            6,
        ) if total else 0.0,
        "per_class": per_class,
        "confusion_matrix": matrix,
        "interpretation": (
            "binary NPA/PA" if len(classes) == 2
            else "applicability + binary diagnostic (three decision states)"
        ),
    }
