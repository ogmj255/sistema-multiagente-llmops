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


# V3: referencia humana definitiva, separada de los pilotos históricos V2.
# Las huellas fueron calculadas sobre ANEXO-GroundTruth_FINAL_corregido_20261106.xlsx.
# El CSV privado NO debe incorporarse a Git ni a la colección jurídica.
V3_PROTOCOL = "NPA-PA-v3.0"
V3_SOURCE_FINGERPRINT = (
    "c59cb35c732d5c51041c22f5c47d923b077a32b9bd2d46e42124ca6fe8275943"
)
V3_SOURCE_SHA256 = (
    "b729651c57a80d6622ad8a5722b3a2fe369842e4c147c988a45a0a6b83215eb0"
)
V3_BINARY_FINGERPRINT = (
    "8dc8ad7b83bd2985eeebcdac7ab55c44580d36ff279844bd818a9bed8a10cd5c"
)
V3_TEXT_SEQUENCE_FINGERPRINT = (
    "00a23131d0da4b41386324e92df6d3a16fb40849ecefcde2d72b71d33d0d54f9"
)


def load_binary_groundtruth_v3(path: str | Path) -> GroundTruth:
    """Carga V3 de forma explícita; nunca reinterpreta V2 como V3."""
    base = load_groundtruth_csv(path)
    if base.fingerprint != V3_SOURCE_FINGERPRINT:
        raise ValueError(
            "El ground truth V3 no coincide con las etiquetas aprobadas. "
            "No utilizar el CSV histórico ni alterar las 547 decisiones."
        )
    if base.source_sha256 != V3_SOURCE_SHA256:
        raise ValueError(
            "El archivo CSV V3 no coincide byte a byte con el manifiesto "
            "aprobado (SHA-256). Restaurar la copia original."
        )
    if any(unit.label not in BINARY_LABELS for unit in base.units):
        raise ValueError("V3 solo admite PA, NPA y aplicabilidad separada.")

    text_sequence = [
        {"id": u.technical_id, "platform": u.platform, "text": u.original_text}
        for u in base.units
    ]
    seq_fp = hashlib.sha256(json.dumps(
        text_sequence,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    if seq_fp != V3_TEXT_SEQUENCE_FINGERPRINT:
        raise ValueError("El orden o los textos originales de V3 cambiaron.")

    mapped = tuple(replace(u, label=BINARY_MAPPING[u.label]) for u in base.units)
    canonical_rows = [
        {
            "id": unit.technical_id,
            "platform": unit.platform,
            "text": unit.original_text,
            "applicability": unit.applicability,
            "label": unit.label,
        }
        for unit in mapped
    ]
    fp = hashlib.sha256(json.dumps(
        {
            "protocol": V3_PROTOCOL,
            "base_fingerprint": base.fingerprint,
            "rows": canonical_rows,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")).hexdigest()
    if fp != V3_BINARY_FINGERPRINT:
        raise ValueError("Fingerprint binario V3 incompatible con el protocolo.")
    return GroundTruth(
        units=mapped,
        fingerprint=fp,
        source_sha256=base.source_sha256,
    )


def binary_manifest_v3(dataset: GroundTruth) -> dict[str, object]:
    """Resumen sin textos sensibles de la referencia V3."""
    from collections import Counter

    if dataset.fingerprint != V3_BINARY_FINGERPRINT:
        raise ValueError("Se requiere el ground truth binario V3 aprobado.")
    counts = Counter(unit.label for unit in dataset.units)
    if (
        len(dataset.units) != 547
        or counts["no potencialmente abusiva"] != 318
        or counts["potencialmente abusiva"] != 156
        or counts["not_applicable"] != 73
    ):
        raise ValueError("Distribución V3 incorrecta.")
    return {
        "protocol": V3_PROTOCOL,
        "base_v1_fingerprint": V3_SOURCE_FINGERPRINT,
        "binary_v3_fingerprint": V3_BINARY_FINGERPRINT,
        "original_source_sha256": V3_SOURCE_SHA256,
        "units": len(dataset.units),
        "applicability": {
            "evaluable": 474,
            "not_applicable": 73,
        },
        "classification_labels": {
            "NPA": 318,
            "PA": 156,
        },
        "mapping": {"not_applicable": "not_applicable",
                    "no potencialmente abusiva": "no potencialmente abusiva",
                    "potencialmente abusiva": "potencialmente abusiva"},
        "do_not_mix_v2_results": True,
    }


def load_versioned_binary_groundtruth(
    path: str | Path, *, version: str = "v2"
) -> GroundTruth:
    """Selecciona la referencia por versión; V2 sigue siendo el valor por defecto."""
    if version == "v2":
        return load_binary_groundtruth_v2(path)
    if version == "v3":
        return load_binary_groundtruth_v3(path)
    raise ValueError(f"Versión de ground truth no permitida: {version}")


def binary_manifest_versioned(
    dataset: GroundTruth, *, version: str = "v2"
) -> dict[str, object]:
    if version == "v2":
        return binary_manifest(dataset)
    if version == "v3":
        return binary_manifest_v3(dataset)
    raise ValueError(f"Protocolo binario no permitido: {version}")
