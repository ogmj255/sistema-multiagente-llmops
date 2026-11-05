"""Puntúa la campaña por tratamiento y repetición, SIN solicitudes externas."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from app.evaluation.groundtruth import load_groundtruth_csv
from app.evaluation.pilot import read_jsonl
from app.evaluation.repetition_metrics import score_campaign_repetitions


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Métricas de 3 modelos × 3 repeticiones, sin inferencia."
    )
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument(
        "--results", type=Path,
        default=Path("data/evaluation/formal_campaign_runs.jsonl"),
    )
    parser.add_argument(
        "--output", type=Path,
        default=Path("data/evaluation/formal_metrics_by_repetition.json"),
    )
    args = parser.parse_args()

    dataset = load_groundtruth_csv(args.csv)
    records = read_jsonl(args.results)
    result = score_campaign_repetitions(dataset, records)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    table = args.output.with_suffix(".csv")
    fields = [
        "treatment", "model", "repetition",
        "documents_completed", "documents_incomplete", "documents_pending",
        "predictions_valid", "missing_or_invalid",
        "accuracy_four_classes", "f1_macro_four_classes",
        "accuracy_evaluable", "f1_macro_evaluable",
        "duration_ms_reported", "cost_usd_reported",
        "is_complete",
    ]
    with table.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in result["by_treatment_repetition"]:
            writer.writerow({
                **{key: row[key] for key in fields if key in row},
                "accuracy_four_classes": row["all_units"]["accuracy"],
                "f1_macro_four_classes": row["all_units"]["f1_macro"],
                "accuracy_evaluable": row["evaluable_units"]["accuracy"],
                "f1_macro_evaluable": row["evaluable_units"]["f1_macro"],
            })

    print(
        f"Tareas registradas: {len(records)} | "
        f"Resultados completos: {result['results_are_final']}"
    )
    print(f"Detalle JSON: {args.output}")
    print(f"Tabla CSV: {table}")


if __name__ == "__main__":
    main()
