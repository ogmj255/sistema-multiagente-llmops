"""Versión V2 binaria, derivada del ground truth histórico inmutable.

Esta proyección NO altera las 547 unidades, los textos ni su orden.
Las decisiones originales conservan integridad SHA y se pueden auditar.
La clasificación de riesgo se reduce a NPA/PA; aplicabilidad es distinta.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

from app.evaluation.groundtruth import (
    GroundTruth, load_groundtruth_csv,
)

V1_DATASET_FINGERPRINT = (
    "47f69eb943f539751f2c120ab6fdd7f45bbc000f93459a90f1162212cfdde4a5"
)
BINARY_CLASSES = (
    "no potencialmente abusiva",
    "potencialmente abusiva",
)
BINARY_LABELS = ("not_applicable", *BINARY_CLASSES)

BINARY_MAPPING = {
    "not_applicable": "not_applicable",
    "no potencialmente abusiva": "no potencialmente abusiva",
    "potencialmente abusiva": "potencialmente abusiva",
    "indicios fuertes de abusividad": "potencialmente abusiva",
}

BINARY_PROTOCOL = "NPA-PA-v2.0"


def project_binary_groundtruth(groundtruth: GroundTruth) -> GroundTruth:
    """Adapta las etiquetas, no reescribe la referencia original."""
    if groundtruth.fingerprint != V1_DATASET_FINGERPRINT:
        raise ValueError(
            "La base histórica no coincide con la huella aprobada V1. "
            "No se puede generar una proyección binaria sin validación."
        )

    mapped = tuple(
        replace(unit, label=BINARY_MAPPING[unit.label])
        for unit in groundtruth.units
    )
    canonical = [
        {
            "id": unit.technical_id,
            "platform": unit.platform,
            "text": unit.original_text,
            "applicability": unit.applicability,
            "label": unit.label,
        }
        for unit in mapped
    ]
    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "protocol": BINARY_PROTOCOL,
                "base_fingerprint": groundtruth.fingerprint,
                "rows": canonical,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return GroundTruth(
        units=mapped,
        fingerprint=fingerprint,
        source_sha256=groundtruth.source_sha256,
    )


def load_binary_groundtruth_v2(
    path: str | Path,
) -> GroundTruth:
    return project_binary_groundtruth(load_groundtruth_csv(path))


def binary_manifest(groundtruth: GroundTruth) -> dict[str, object]:
    from collections import Counter

    counts = Counter(unit.label for unit in groundtruth.units)
    return {
        "protocol": BINARY_PROTOCOL,
        "base_v1_fingerprint": V1_DATASET_FINGERPRINT,
        "binary_v2_fingerprint": groundtruth.fingerprint,
        "original_source_sha256": groundtruth.source_sha256,
        "units": len(groundtruth.units),
        "applicability": {
            "evaluable": counts["no potencialmente abusiva"] + counts["potencialmente abusiva"],
            "not_applicable": counts["not_applicable"],
        },
        "classification_labels": {
            "NPA": counts["no potencialmente abusiva"],
            "PA": counts["potencialmente abusiva"],
        },
        "mapping": BINARY_MAPPING,
        "do_not_mix_v1_results": True,
    }
