"""Puntúa la campaña por tratamiento y repetición, SIN solicitudes externas."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from app.evaluation.binary_groundtruth import load_versioned_binary_groundtruth
from app.evaluation.document_metrics import score_campaign_documents
from app.evaluation.pilot import read_jsonl
from app.evaluation.repetition_metrics import score_campaign_repetitions


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Métricas de 3 modelos × 3 repeticiones, sin inferencia."
    )
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument(
        "--protocol", choices=("v2", "v3"), default="v2",
    )
    parser.add_argument(
        "--results", type=Path,
        default=None,
    )
    parser.add_argument(
        "--output", type=Path,
        default=None,
    )
    args = parser.parse_args()
    prefix = "v3_binary" if args.protocol == "v3" else "v2_binary"
    if args.protocol == "v3" and args.csv.name != "ground_truth_547_v3.csv":
        parser.error("V3 exige ground_truth_547_v3.csv.")
    if args.results is None:
        args.results = args.csv.parent / f"{prefix}_campaign_runs.jsonl"
    if args.output is None:
        args.output = args.csv.parent / f"{prefix}_metrics_by_repetition.json"
    if args.protocol == "v3" and (
        "v2_binary" in str(args.results) or "v2_binary" in str(args.output)
    ):
        parser.error("No mezclar resultados o métricas V2 con V3.")
    dataset = load_versioned_binary_groundtruth(
        args.csv, version=args.protocol
    )
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
        "coverage_decision_status",
        "pending_document_units",
        "unavailable_in_started_documents",
        "explicit_unit_errors",
        "accuracy_status_diagnostic", "f1_macro_status_diagnostic",
        "accuracy_binary_NPA_PA", "f1_macro_binary_NPA_PA",
        "accuracy_status_coverage_adjusted",
        "f1_macro_status_coverage_adjusted",
        "duration_ms_reported", "cost_usd_reported",
        "is_complete",
    ]
    with table.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in result["by_treatment_repetition"]:
            writer.writerow({
                **{key: row[key] for key in fields if key in row},
                # Si faltan documentos, NO publicar 1,28% como si
                # fuera la exactitud de DeepSeek sobre Holded.
                "coverage_decision_status": row["all_units"]["coverage"],
                "accuracy_status_diagnostic": (
                    row["all_units"]["accuracy"] if row["is_complete"]
                    else None
                ),
                "f1_macro_status_diagnostic": (
                    row["all_units"]["f1_macro"] if row["is_complete"]
                    else None
                ),
                "accuracy_binary_NPA_PA": (
                    row["evaluable_units"]["accuracy"] if row["is_complete"]
                    else None
                ),
                "f1_macro_binary_NPA_PA": (
                    row["evaluable_units"]["f1_macro"] if row["is_complete"]
                    else None
                ),
                "accuracy_status_coverage_adjusted": (
                    row["all_units"]["accuracy"]
                ),
                "f1_macro_status_coverage_adjusted": (
                    row["all_units"]["f1_macro"]
                ),
            })

    # Calidad documental: denominador = unidades del ToS realmente
    # analizadas. Nunca presentar como 0 una tarea no ejecutada.
    documents = score_campaign_documents(dataset, records)
    document_table = args.output.with_name(
        f"{prefix}_metrics_by_document.csv"
    )
    document_fields = [
        "task_id", "document_id", "platform", "treatment", "model",
        "repetition", "status", "unit_count", "predictions_valid",
        "predictions_missing", "explicit_unit_errors", "attempt_records",
        "correct_on_observed", "accuracy_on_observed",
        "f1_macro_on_observed", "accuracy_binary_NPA_PA_observed",
        "f1_macro_binary_NPA_PA_observed", "quality_is_final_for_document",
        "duration_ms_reported", "cost_usd_reported",
        "cost_reporting_incomplete_attempts",
    ]
    with document_table.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=document_fields)
        writer.writeheader()
        for row in documents:
            writer.writerow({key: row.get(key) for key in document_fields})

    document_details = args.output.with_name(
        f"{prefix}_metrics_by_document.json"
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
