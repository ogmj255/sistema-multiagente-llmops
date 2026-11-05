"""Puntúa la campaña por tratamiento y repetición, SIN solicitudes externas."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from app.evaluation.groundtruth import load_groundtruth_csv
from app.evaluation.document_metrics import score_campaign_documents
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

    # Calidad documental: denominador = unidades del ToS realmente
    # analizadas. Nunca presentar como 0 una tarea no ejecutada.
    documents = score_campaign_documents(dataset, records)
    document_table = args.output.with_name(
        "formal_metrics_by_document.csv"
    )
    document_fields = [
        "task_id", "document_id", "platform", "treatment", "model",
        "repetition", "status", "unit_count", "predictions_valid",
        "predictions_missing", "explicit_unit_errors", "attempt_records",
        "correct_on_observed", "accuracy_on_observed",
        "f1_macro_on_observed", "accuracy_evaluable_observed",
        "f1_macro_evaluable_observed", "quality_is_final_for_document",
        "duration_ms_reported", "cost_usd_reported",
        "cost_reporting_incomplete_attempts",
    ]
    with document_table.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=document_fields)
        writer.writeheader()
        for row in documents:
            writer.writerow({key: row.get(key) for key in document_fields})

    document_details = args.output.with_name(
        "formal_metrics_by_document.json"
    )
    document_details.write_text(
        json.dumps({
            "dataset_fingerprint": dataset.fingerprint,
            "scope": "90 independent document/model/repetition tasks",
            "documents": documents,
            "notes": (
                "La exactitud observada usa solo las unidades clasificadas "
                "del documento, sin imputar unidades pendientes como errores. "
                "La calidad documental solo es definitiva si "
                "quality_is_final_for_document=true. Las 547 unidades "
                "permanecen como denominador para cobertura global."
            ),
        }, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(
        f"Tareas registradas: {len(records)} | "
        f"Resultados completos: {result['results_are_final']}"
    )
    print(f"Detalle JSON: {args.output}")
    print(f"Tabla CSV: {table}")
    print(f"Métricas por documento: {document_table}")
    print(f"Matrices por documento: {document_details}")


if __name__ == "__main__":
    main()
