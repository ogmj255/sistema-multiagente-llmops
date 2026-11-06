"""Inspección humana de cuatro decisiones de aplicabilidad en ET04-R1.

Imprime texto original del ground truth (SOLO LECTURA) y la justificación
ya emitida por ambos LLM. No realiza inferencias, mutaciones o llamadas
a OpenRouter, LangGraph ni herramientas MCP. El preflight puede consultar
Chroma/Ollama para comprobar las huellas.

Ejemplo:
    python -m scripts.inspect_v21_disagreements_readonly
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.evaluation.binary_groundtruth import load_binary_groundtruth_v2
from app.evaluation.campaign import document_units
from app.evaluation.design import make_experimental_plan
from scripts.validate_v21_holdout import (
    BASELINE_RESULTS, CANDIDATE_RESULTS, TARGET_TASK_ID,
    _completed_record, _root, verify_holdout,
)

DEFAULT_IDS = ("ToS02-U001", "ToS02-U002", "ToS02-U011", "ToS02-U023")


def inspect(data_dir: Path, ids_to_review: tuple[str, ...] = DEFAULT_IDS) -> list[dict[str, Any]]:
    """No escribe resultados ni interpreta las justificaciones automáticamente."""
    frozen = verify_holdout(data_dir)
    dataset = load_binary_groundtruth_v2(data_dir / "ground_truth_547.csv")
    task = next(
        task for task in make_experimental_plan(dataset)["tasks"]
        if task["task_id"] == TARGET_TASK_ID
    )
    units = document_units(dataset, task)
    by_id = {unit.technical_id: unit for unit in units}
    invalid = sorted(set(ids_to_review) - set(by_id))
    if invalid:
        raise ValueError(f"IDs ajenos al documento congelado: {invalid}")

    root = _root(data_dir)
    expected_ids = [unit.technical_id for unit in units]
    base = _completed_record(
        root / BASELINE_RESULTS, task, expected_ids, dataset.fingerprint
    )
    v21 = _completed_record(
        root / CANDIDATE_RESULTS, task, expected_ids, dataset.fingerprint
    )
    if v21.get("holdout_manifest_fingerprint") != frozen["fingerprint"]:
        raise ValueError("Huella de la candidata incompatible con el holdout.")

    responses = {
        "v2": {row["id"]: row for row in base["unit_results"]},
        "v21": {row["id"]: row for row in v21["unit_results"]},
    }
    report: list[dict[str, Any]] = []
    for unit_id in ids_to_review:
        unit = by_id[unit_id]
        one = {
            "id": unit_id,
            "platform": unit.platform,
            "original_text_complete": unit.original_text,
            "reference_label": unit.label,
            "reference_applicability": unit.applicability,
            "responses": {},
        }
        for version in ("v2", "v21"):
            result = responses[version][unit_id]
            assessment = result.get("assessment")
            if not isinstance(assessment, dict):
                raise ValueError(f"{version}: falta análisis estructurado para {unit_id}")
            one["responses"][version] = {
                "prediction": result.get("prediction"),
                "analysis_status": assessment.get("analysis_status"),
                "classification": assessment.get("classification"),
                "justification": assessment.get("justification"),
                "recommendation": assessment.get("recommendation"),
                "evidence_sufficiency": assessment.get("evidence_sufficiency"),
                "category": assessment.get("category"),
                "clause_type": assessment.get("clause_type"),
            }
        report.append(one)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir", type=Path, default=Path("data/evaluation")
    )
    parser.add_argument(
        "--ids", nargs="+", default=list(DEFAULT_IDS),
        help="IDs para inspección manual; predeterminado: 4 discordancias."
    )
    args = parser.parse_args()
    print(json.dumps(
        {
            "type": "READ_ONLY_HUMAN_APPLICABILITY_REVIEW",
            "task_id": TARGET_TASK_ID,
            "review_only": True,
            "items": inspect(args.data_dir.resolve(), tuple(args.ids)),
            "notes": [
                "No se modifica el ground truth ni ninguna predicción.",
                "Comparar el contenido del fragmento con la rúbrica de aplicabilidad.",
                "Las observaciones humanas son posteriores a la prueba holdout.",
            ],
        },
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
