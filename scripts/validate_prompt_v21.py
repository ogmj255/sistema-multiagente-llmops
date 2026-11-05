"""Piloto V2.1 aislado: prompt nuevo contra ET01-R1 V2 (solo Holded).

Usa LangGraph y MCP reales a través de run_orchestrated_trial; no hay
llamadas directas al proveedor. No toca manifiesto, predicciones ni
checkpoints V2. Nunca lanza 90 tareas automáticamente.

Modos: --freeze (sin facturación), --verify, --compare (sin facturación)
y --execute (requiere doble confirmación, puede consumir créditos).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.evaluation.binary_groundtruth import load_binary_groundtruth_v2
from app.evaluation.campaign import (
    completed_document_run, document_units, sum_reported_cost,
)
from app.evaluation.design import make_experimental_plan
from app.evaluation.document_metrics import score_campaign_documents
from app.evaluation.orchestrated import run_orchestrated_trial
from app.evaluation.pilot import append_jsonl, canonical_sha256, read_jsonl
from app.evaluation.readiness import PreflightError, create_readiness_manifest

CANDIDATE_PROTOCOL = "NPA-PA-v2.1-candidate"
TASK_ID = "ET01-R1"
OLD_RUN_FILENAME = "v2_binary_campaign_runs.jsonl"
OLD_PREFLIGHT_FILENAME = "v2_binary_preflight_manifest.json"
CANDIDATE_FOLDER = "prompt_v2_1_candidate"
CANDIDATE_PREFLIGHT_FILENAME = "preflight_manifest.json"
CANDIDATE_RUN_FILENAME = "runs.jsonl"
CANDIDATE_CHECKPOINTS_FILENAME = "unit_checkpoints.jsonl"
CANDIDATE_RAG_FILENAME = "legal_context_snapshots.jsonl"

NPA = "no potencialmente abusiva"
PA = "potencialmente abusiva"


def candidate_directory(root: Path) -> Path:
    return root / CANDIDATE_FOLDER


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PreflightError(f"Falta archivo requerido: {path.name}")
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise PreflightError(f"JSON inválido: {path.name}") from error
    if not isinstance(parsed, dict):
        raise PreflightError(f"El archivo {path.name} debe ser un objeto JSON.")
    return parsed


def _source_hash() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _candidate_state(root: Path) -> dict[str, Any]:
    """Comparación de entorno sin incluir ni modificar el manifiesto V2."""
    original = _load_json(root / OLD_PREFLIGHT_FILENAME)
    baseline = original.get("environment")
    if not isinstance(baseline, dict):
        raise PreflightError("El preflight original V2 no contiene entorno válido.")
    current = create_readiness_manifest(root)
    controlled_fields = (
        "dataset_fingerprint", "source_sha256", "labels", "applicability",
        "tasks", "expected_predictions", "model_ids", "llm_temperature",
        "openrouter_endpoint", "langfuse_tracing_enabled", "rag", "ollama",
    )
    differences = [
        name for name in controlled_fields
        if baseline.get(name) != current.get(name)
    ]
    if differences:
        raise PreflightError(
            "Se modificaron variables controladas con respecto a V2: "
            + ", ".join(differences)
        )
    if baseline.get("config_sha256") == current.get("config_sha256"):
        raise PreflightError(
            "El prompt/configuración es idéntico a V2: no hay variante candidata."
        )
    if original.get("fingerprint") != canonical_sha256(baseline):
        raise PreflightError("La huella del preflight original V2 es inválida.")
    return {
        "candidate_protocol": CANDIDATE_PROTOCOL,
        "baseline_preflight_sha256": original["fingerprint"],
        "environment": current,
        "candidate_runner_sha256": _source_hash(),
    }


def _new_manifest(root: Path) -> dict[str, Any]:
    payload = _candidate_state(root)
    return {
        "fingerprint": canonical_sha256(payload),
        "frozen_at_utc": datetime.now(UTC).isoformat(),
        "candidate": payload,
    }


def freeze_candidate(root: Path) -> dict[str, Any]:
    """Crear una única vez: jamás sobrescribir un manifiesto diferente."""
    target = candidate_directory(root) / CANDIDATE_PREFLIGHT_FILENAME
    if target.exists():
        return verify_candidate(root)
    payload = _new_manifest(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with target.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as error:
        raise PreflightError("Otro proceso creó el preflight V2.1.") from error
    return payload


def verify_candidate(root: Path) -> dict[str, Any]:
    target = candidate_directory(root) / CANDIDATE_PREFLIGHT_FILENAME
    frozen = _load_json(target)
    actual = _candidate_state(root)
    if frozen.get("fingerprint") != canonical_sha256(actual):
        raise PreflightError(
            "La candidata, la referencia, el código o el RAG cambiaron "
            "después de congelarse; no se permite inferencia."
        )
    return frozen


def _task_and_dataset(root: Path):
    dataset = load_binary_groundtruth_v2(root / "ground_truth_547.csv")
    plan = make_experimental_plan(dataset)
    task = next(
        (item for item in plan["tasks"] if item["task_id"] == TASK_ID),
        None,
    )
    if task is None or int(task["unit_count"]) != 21:
        raise ValueError("El diseño de Holded no coincide con ET01-R1 V2.")
    units = document_units(dataset, task)
    return dataset, task, units


def _completed_row(
    records: list[dict[str, Any]],
    task: dict[str, Any],
    ids: list[str],
    fingerprint: str,
) -> dict[str, Any] | None:
    for row in reversed(records):
        if completed_document_run(row, task, ids, fingerprint):
            return row
    return None


def _baseline_completed(root: Path, dataset, task, units) -> dict[str, Any]:
    baseline_records = read_jsonl(root / OLD_RUN_FILENAME)
    baseline = _completed_row(
        baseline_records, task, [u.technical_id for u in units],
        dataset.fingerprint,
    )
    if baseline is None:
        raise ValueError(
            "No existe ET01-R1 V2 completa y verificable. "
            "Se prohíbe una comparación sin referencia."
        )
    return baseline


def _no_active_v2_jobs(root: Path) -> None:
    job_dir = root / "binary_jobs"
    for path in job_dir.glob("*.json"):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as error:
            raise PreflightError(
                "Existe una orden V2 ilegible; no se iniciará una candidata."
            ) from error
        if row.get("status") in {"queued", "running"}:
            raise PreflightError(
                "Hay tareas V2 en cola o ejecución; no lanzar la candidata."
            )


def _compare_one(root: Path) -> dict[str, Any]:
    dataset, task, units = _task_and_dataset(root)
    old = _baseline_completed(root, dataset, task, units)
    new_records = read_jsonl(
        candidate_directory(root) / CANDIDATE_RUN_FILENAME
    )
    new = _completed_row(
        new_records, task, [u.technical_id for u in units],
        dataset.fingerprint,
    )
    if new is None:
        raise ValueError(
            "El piloto V2.1 no está completo: no se puede comparar."
        )
    old_metrics = next(
        row for row in score_campaign_documents(dataset, [old])
        if row["task_id"] == TASK_ID
    )
    new_metrics = next(
        row for row in score_campaign_documents(dataset, [new])
        if row["task_id"] == TASK_ID
    )
    old_matrix = old_metrics["binary_confusion_matrix_on_observed"]
    new_matrix = new_metrics["binary_confusion_matrix_on_observed"]

    def row_summary(metrics, matrix):
        return {
            "accuracy": metrics["accuracy_evaluable_observed"],
            "f1_macro": metrics["f1_macro_evaluable_observed"],
            "false_positives": matrix[NPA][PA],
            "false_negatives": matrix[PA][NPA],
            "true_positives": matrix[PA][PA],
            "true_negatives": matrix[NPA][NPA],
            "npa_f1": metrics["binary_per_class_on_observed"][NPA]["f1"],
            "pa_precision": metrics["binary_per_class_on_observed"][PA]["precision"],
            "pa_recall": metrics["binary_per_class_on_observed"][PA]["recall"],
            "reported_cost_usd": metrics["cost_usd_reported"],
            "duration_ms_reported": metrics["duration_ms_reported"],
            "cost_reporting_incomplete_attempts":
                metrics["cost_reporting_incomplete_attempts"],
        }

    original = row_summary(old_metrics, old_matrix)
    candidate = row_summary(new_metrics, new_matrix)
    old_by_id = {r["id"]: r["prediction"] for r in old["unit_results"]}
    new_by_id = {r["id"]: r["prediction"] for r in new["unit_results"]}
    changed = [
        {
            "id": unit.technical_id,
            "human_reference": unit.label,
            "v2_prediction": old_by_id[unit.technical_id],
            "v2_1_prediction": new_by_id[unit.technical_id],
        }
        for unit in units
        if old_by_id[unit.technical_id] != new_by_id[unit.technical_id]
    ]
    preliminary_improvement = (
        candidate["f1_macro"] > original["f1_macro"]
        and candidate["false_negatives"] <= original["false_negatives"]
        and candidate["false_positives"] < original["false_positives"]
        and new_metrics["predictions_valid"] == 21
    )
    report = {
        "comparison_type": "EXPLORATORY_NOT_CONFIRMATORY",
        "protocols": ["NPA-PA-v2.0", CANDIDATE_PROTOCOL],
        "task_id": TASK_ID,
        "dataset_fingerprint": dataset.fingerprint,
        "baseline_execution_id": old.get("execution_id"),
        "candidate_execution_id": new.get("execution_id"),
        "baseline": original,
        "candidate": candidate,
        "delta": {
            "accuracy": round(candidate["accuracy"] - original["accuracy"], 6),
            "f1_macro": round(candidate["f1_macro"] - original["f1_macro"], 6),
            "false_positives": (
                candidate["false_positives"] - original["false_positives"]
            ),
            "false_negatives": (
                candidate["false_negatives"] - original["false_negatives"]
            ),
        },
        "changed_unit_predictions": changed,
        "candidate_passes_exploratory_gate": preliminary_improvement,
        "limitations": [
            "La candidata se evaluó después de inspeccionar los errores V2.",
            "Un único documento con solo cuatro PA no prueba superioridad.",
            "La generación fallida V2 podría no estar incluida en el costo",
            "No se debe seleccionar la mejor variante por la misma muestra "
            "y reportarla como confirmación estadística.",
        ],
    }
    destination = candidate_directory(root) / "comparison.json"
    destination.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


async def _run_one(root: Path, budget: float) -> dict[str, Any]:
    dataset, task, units = _task_and_dataset(root)
    _baseline_completed(root, dataset, task, units)
    output_dir = candidate_directory(root)
    output = output_dir / CANDIDATE_RUN_FILENAME
    previous = read_jsonl(output)
    ids = [unit.technical_id for unit in units]
    if _completed_row(previous, task, ids, dataset.fingerprint):
        raise ValueError(
            "La candidata ET01-R1 ya está completa; no generar otra factura."
        )
    if previous:
        raise ValueError(
            "Existe un intento previo V2.1. Audítalo antes de reanudar; "
            "no está habilitado el reintento automático."
        )

    lock = output_dir / "candidate_execution.lock"
    try:
        lock_fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise PreflightError("Otra ejecución V2.1 está activa.") from error
    try:
        os.write(lock_fd, str(os.getpid()).encode("ascii"))
        os.close(lock_fd)
        verify_candidate(root)
        _no_active_v2_jobs(root)
        print(
            f"EJECUCIÓN PAGADA V2.1: {TASK_ID}, {task['model']}, "
            f"{len(units)} cláusulas. Límite BLANDO reportado: USD {budget:.4f}",
            flush=True,
        )
        try:
            result = await run_orchestrated_trial(
                units,
                task=task,
                dataset_fingerprint=dataset.fingerprint,
                context_cache=output_dir / CANDIDATE_RAG_FILENAME,
                checkpoint_path=output_dir / CANDIDATE_CHECKPOINTS_FILENAME,
            )
        except Exception as error:
            result = {
                "task_id": task["task_id"],
                "combination_id": task["combination_id"],
                "treatment": task["treatment"],
                "model": task["model"],
                "repetition": task["repetition"],
                "document_id": task["document_id"],
                "dataset_fingerprint": dataset.fingerprint,
                "status": "execution_error",
                "unit_results": [],
                "llm_metrics": [],
                "error_type": type(error).__name__,
                "error": str(error)[:1500],
                "reported_cost_incomplete": True,
            }
        result["candidate_profile"] = CANDIDATE_PROTOCOL
        result["candidate_manifest_fingerprint"] = _load_json(
            output_dir / CANDIDATE_PREFLIGHT_FILENAME
        )["fingerprint"]
        append_jsonl(output, result)
        print(
            "Estado=", result["status"],
            "Costo reportado USD=", round(sum_reported_cost(result), 6),
            "(no incluye necesariamente intentos rechazados)",
            flush=True,
        )
        return result
    finally:
        lock.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Comparación exploratoria de prompt V2 contra V2.1"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--freeze", action="store_true")
    group.add_argument("--verify", action="store_true")
    group.add_argument("--execute", action="store_true")
    group.add_argument("--compare", action="store_true")
    parser.add_argument(
        "--data-dir", type=Path,
        default=Path(os.getenv("EXPERIMENT_DATA_DIR", "data/evaluation")),
    )
    parser.add_argument("--confirm-paid-run", action="store_true")
    parser.add_argument("--max-reported-cost-usd", type=float)
    args = parser.parse_args()
    root = args.data_dir.resolve()
    if args.freeze:
        record = freeze_candidate(root)
        print("PREFLIGHT V2.1 CONGELADO; no se invocó OpenRouter.")
        print("Huella candidata:", record["fingerprint"])
    elif args.verify:
        record = verify_candidate(root)
        print("PREFLIGHT V2.1 APROBADO; no se invocó OpenRouter.")
        print("Huella candidata:", record["fingerprint"])
    elif args.compare:
        report = _compare_one(root)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        if (
            not args.confirm_paid_run
            or os.getenv("V21_CANDIDATE_EXECUTION_ENABLED", "false").lower()
            != "true"
        ):
            parser.error(
                "Para inferencia real exige --confirm-paid-run y "
                "V21_CANDIDATE_EXECUTION_ENABLED=true."
            )
        if (
            args.max_reported_cost_usd is None
            or not math.isfinite(args.max_reported_cost_usd)
            or args.max_reported_cost_usd <= 0
        ):
            parser.error(
                "--max-reported-cost-usd debe ser positivo y explícito "
                "(NO es un límite duro durante el documento)."
            )
        if os.getenv("EXPERIMENT_EXECUTION_ENABLED", "false").lower() == "true":
            parser.error(
                "Deshabilita primero la facturación del módulo V2 "
                "EXPERIMENT_EXECUTION_ENABLED=false."
            )
        verify_candidate(root)
        _no_active_v2_jobs(root)
        result = asyncio.run(_run_one(root, args.max_reported_cost_usd))
        if result["status"] == "success":
            print(
                "Para comparar sin facturación, usa --compare. "
                "No hay lanzamiento de 90 tareas."
            )
        else:
            raise SystemExit(
                "El piloto no terminó correctamente. Preserva el registro "
                "y audita el error antes de cualquier reintento."
            )


if __name__ == "__main__":
    main()
