"""Verifica referencia V3 sin OpenRouter, Docker, MCP, Ollama ni Chroma.

Ejemplo (PowerShell, raíz del proyecto):
  $env:PYTHONPATH = (Resolve-Path ".\backend").Path
  python -m scripts.verify_groundtruth_v3 --csv data/evaluation/ground_truth_547_v3.csv
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.evaluation.binary_groundtruth import (
    V3_SOURCE_SHA256, binary_manifest_v3, load_binary_groundtruth_v3,
)
from app.evaluation.design import make_experimental_plan


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--csv", type=Path, required=True,
        help="Referencia privada ground_truth_547_v3.csv ya exportada.",
    )
    args = parser.parse_args()
    dataset = load_binary_groundtruth_v3(args.csv)
    summary = binary_manifest_v3(dataset)
    plan = make_experimental_plan(dataset)
    if plan["executions"] != 90 or plan["expected_unit_predictions"] != 4923:
        raise SystemExit("Bloqueado: se esperaba 90 tareas / 4923 salidas.")
    if dataset.source_sha256 != V3_SOURCE_SHA256:
        raise SystemExit("Bloqueado: checksum CSV distinto del autorizado.")
    print(json.dumps({
        "status": "V3_REFERENCE_VERIFIED_NO_INFERENCE",
        "dataset": summary,
        "tasks": plan["executions"],
        "expected_classifications": plan["expected_unit_predictions"],
        "preview_tasks": [
            {
                "task_id": x["task_id"], "document_id": x["document_id"],
                "model": x["model"], "unit_count": x["unit_count"],
            }
            for x in plan["tasks"][:3]
        ],
    }, indent=2, ensure_ascii=False))
    print("No se consultaron OpenRouter, MCP, Chroma ni Ollama.")


if __name__ == "__main__":
    main()
