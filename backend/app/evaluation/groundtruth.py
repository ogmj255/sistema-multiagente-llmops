"""Carga verificable del ground truth sin transformar los textos originales."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

LABELS = (
    "not_applicable",
    "no potencialmente abusiva",
    "potencialmente abusiva",
    "indicios fuertes de abusividad",
)
HEADERS = (
    "ID técnico",
    "Plataforma",
    "Cláusula original completa",
    "Aplicabilidad",
    "Etiqueta final",
)
ID_PATTERN = re.compile(r"ToS\d{2}-U\d{3}\Z")


class GroundTruthError(ValueError):
    """El corpus no supera las verificaciones de integridad."""


@dataclass(frozen=True, slots=True)
class GroundTruthUnit:
    technical_id: str
    platform: str
    original_text: str
    applicability: str
    label: str
    text_sha256: str

    def model_input(self) -> dict[str, str]:
        """Proyección sin etiqueta humana: única entrada autorizada al LLM."""
        return {
            "id": self.technical_id,
            "platform": self.platform,
            "text": self.original_text,
        }


@dataclass(frozen=True, slots=True)
class GroundTruth:
    units: tuple[GroundTruthUnit, ...]
    fingerprint: str
    source_sha256: str

    def manifest(self) -> dict[str, object]:
        return {
            "units": len(self.units),
            "fingerprint": self.fingerprint,
            "source_sha256": self.source_sha256,
            "labels": dict(Counter(unit.label for unit in self.units)),
            "platforms": dict(Counter(unit.platform for unit in self.units)),
        }


def load_groundtruth_csv(
    path: str | Path,
    *,
    expected_count: int | None = 547,
) -> GroundTruth:
    """Importa un CSV UTF-8 exportado del anexo, sin corregir etiquetas."""
    source = Path(path)
    source_bytes = source.read_bytes()

    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != HEADERS:
            raise GroundTruthError(
                "Cabeceras incorrectas: se requieren las cinco "
                "columnas de ANEXO-GroundTruth, en orden."
            )
        raw_rows = list(reader)

    if expected_count is not None and len(raw_rows) != expected_count:
        raise GroundTruthError(
            f"Se esperaban {expected_count} unidades; se encontraron "
            f"{len(raw_rows)}."
        )

    units: list[GroundTruthUnit] = []
    seen: set[str] = set()

    for position, row in enumerate(raw_rows, start=2):
        technical_id = (row["ID técnico"] or "").strip()
        platform = (row["Plataforma"] or "").strip()
        original = row["Cláusula original completa"]
        applicability = (row["Aplicabilidad"] or "").strip()
        label = (row["Etiqueta final"] or "").strip()

        if not ID_PATTERN.fullmatch(technical_id):
            raise GroundTruthError(
                f"Fila {position}: ID técnico inválido: {technical_id!r}."
            )
        if technical_id in seen:
            raise GroundTruthError(f"ID duplicado: {technical_id}.")
        seen.add(technical_id)

        if not platform or not isinstance(original, str) or not original.strip():
            raise GroundTruthError(
                f"Fila {position}: falta plataforma o texto original."
            )
        if label not in LABELS:
            raise GroundTruthError(
                f"Fila {position}: etiqueta no admitida: {label!r}."
            )
        if applicability not in {"Evaluable", "No aplicable"}:
            raise GroundTruthError(
                f"Fila {position}: aplicabilidad no admitida."
            )
        if (label == "not_applicable") != (applicability == "No aplicable"):
            raise GroundTruthError(
                f"Fila {position}: etiqueta y aplicabilidad incompatibles."
            )

        units.append(
            GroundTruthUnit(
                technical_id=technical_id,
                platform=platform,
                original_text=original,
                applicability=applicability,
                label=label,
                text_sha256=hashlib.sha256(
                    original.encode("utf-8")
                ).hexdigest(),
            )
        )

    canonical_rows = [
        {
            "id": unit.technical_id,
            "platform": unit.platform,
            "text": unit.original_text,
            "applicability": unit.applicability,
            "label": unit.label,
        }
        for unit in units
    ]
    fingerprint = hashlib.sha256(
        json.dumps(
            canonical_rows,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    return GroundTruth(
        units=tuple(units),
        fingerprint=fingerprint,
        source_sha256=hashlib.sha256(source_bytes).hexdigest(),
    )
