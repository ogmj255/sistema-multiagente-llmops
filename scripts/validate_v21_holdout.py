"""Validación apareada pre-registrada en un documento NO usado para ajustar V2.1.

Documento: ToS02 OpenAI, tratamiento T1 DeepSeek, repetición R1 (ET04-R1).
La V2 base se ejecuta desde su rama histórica, con archivos separados.
La candidata usa el mismo LangGraph/MCP/RAG real, nunca llamadas LLM directas.
Este archivo es ADICIONAL: no cambia los hashes ya congelados V2/V2.1.

--freeze / --verify / --compare: sin llamadas a OpenRouter.
--execute-candidate: una sola tarea documentada, pagada y autorizada.
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
from app.evaluation.readiness import PreflightError
from scripts.validate_prompt_v21 import (
    _no_active_v2_jobs, verify_candidate,
)

TARGET_TASK_ID = "ET04-R1"  # ToS02 OpenAI, T1 DeepSeek, R1, 40 cláusulas
TARGET_DOC_ID = "ToS02"
TARGET_UNITS = 40
DIRNAME = "v21_holdout_tos02"
FROZEN_MANIFEST = "preflight_manifest.json"
BASELINE_RESULTS = Path("v2_baseline/runs.jsonl")
CANDIDATE_RESULTS = Path("v21_candidate/runs.jsonl")
CANDIDATE_CHECKPOINTS = Path("v21_candidate/unit_checkpoints.jsonl")
CANDIDATE_RAG = Path("v21_candidate/legal_context_snapshots.jsonl")
NPA = "no potencialmente abusiva"
PA = "potencialmente abusiva"

# Criterios pre-registrados. No alterarlos después de observar resultados.
PREDEFINED_GATE = {
    "f1_macro_minimum_delta": 0.02,
    "false_negatives_must_not_increase": True,
    "not_applicable_correct_must_not_decrease": True,
    "candidate_must_be_complete": True,
    "report_result_as_confirmatory": False,
}


def _root(data_dir: Path) -> Path:
    return data_dir.resolve() / DIRNAME


def _load_object(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PreflightError(f"Falta el archivo: {path}")
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as error:
        raise PreflightError(f"JSON inválido: {path}") from error
    if not isinstance(result, dict):
        raise PreflightError(f"Se esperaba objeto JSON: {path}")
    return result


def _task(dataset):
    plan = make_experimental_plan(dataset)
    chosen = next(
        (item for item in plan["tasks"] if item["task_id"] == TARGET_TASK_ID),
        None,
    )
    if (
        chosen is None
        or chosen["document_id"] != TARGET_DOC_ID
        or chosen["treatment"] != "T1"
        or chosen["repetition"] != 1
        or chosen["unit_count"] != TARGET_UNITS
    ):
        raise PreflightError("La tarea holdout no coincide con el plan de 90 tareas.")
    return chosen, document_units(dataset, chosen)


def _holdout_frozen_payload(data_dir: Path) -> dict[str, Any]:
    """Coteja los dos preflights originales sin reescribir ninguno."""
    historical = _load_object(data_dir / "v2_binary_preflight_manifest.json")
    candidate = verify_candidate(data_dir)
    old_env = historical.get("environment")
    if not isinstance(old_env, dict):
        raise PreflightError("Manifiesto histórico V2 incompleto.")
    if historical.get("fingerprint") != canonical_sha256(old_env):
        raise PreflightError("Huella histórica V2 inválida.")
    cand = candidate.get("candidate")
    if not isinstance(cand, dict):
        raise PreflightError("Manifiesto candidato V2.1 incompleto.")
    if cand.get("baseline_preflight_sha256") != historical["fingerprint"]:
        raise PreflightError("V2.1 no corresponde a la V2 histórica.")
    ds = load_binary_groundtruth_v2(data_dir / "ground_truth_547.csv")
    task, units = _task(ds)
    if (
        ds.fingerprint != old_env.get("dataset_fingerprint")
        or ds.fingerprint != cand["environment"].get("dataset_fingerprint")
    ):
        raise PreflightError("El ground truth no coincide con ambos preflights.")
    return {
        "profile": "V2.1_holdout_pre_registered",
        "dataset_fingerprint": ds.fingerprint,
        "v2_preflight_fingerprint": historical["fingerprint"],
        "v21_candidate_preflight_fingerprint": candidate["fingerprint"],
        "source_sha256": ds.source_sha256,
        "target_task": task,
        "target_ids_sha256": canonical_sha256(
            [unit.technical_id for unit in units]
        ),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "comparison_gate": PREDEFINED_GATE,
        "outputs": {
            "v2_baseline": str(BASELINE_RESULTS),
            "v21_candidate": str(CANDIDATE_RESULTS),
        },
    }


def freeze_holdout(data_dir: Path) -> dict[str, Any]:
    payload = _holdout_frozen_payload(data_dir)
    record = {
        "fingerprint": canonical_sha256(payload),
        "created_at": datetime.now(UTC).isoformat(),
        "pre_registered": payload,
    }
    folder = _root(data_dir)
    destination = folder / FROZEN_MANIFEST
    folder.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        return verify_holdout(data_dir)
    with destination.open("x", encoding="utf-8") as handle:
        json.dump(record, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    return record


def verify_holdout(data_dir: Path) -> dict[str, Any]:
    record = _load_object(_root(data_dir) / FROZEN_MANIFEST)
    payload = _holdout_frozen_payload(data_dir)
    if (
        record.get("fingerprint") != canonical_sha256(payload)
        or record.get("pre_registered") != payload
    ):
        raise PreflightError(
            "El protocolo holdout, los prompts, el RAG o el código cambiaron. "
            "Se bloquea la ejecución."
        )
    return record


def _completed_record(
    path: Path, task: dict[str, Any], ids: list[str], fp: str
) -> dict[str, Any]:
    rows = read_jsonl(path)
    matches = [
        row for row in rows
        if completed_document_run(row, task, ids, fp)
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Se requiere exactamente una tarea completa y única en {path}; "
            f"halladas {len(matches)}. No ejecutar ni comparar sin auditar."
        )
    if len(rows) != 1:
        raise ValueError(
            f"El archivo {path} contiene {len(rows)} intentos. "
            "Auditar antes de aceptar comparabilidad."
        )
    return matches[0]


def _units(data_dir: Path):
    ds = load_binary_groundtruth_v2(data_dir / "ground_truth_547.csv")
    task, units = _task(ds)
    return ds, task, units, [u.technical_id for u in units]


async def execute_candidate(data_dir: Path, budget: float) -> dict[str, Any]:
    frozen = verify_holdout(data_dir)
    _no_active_v2_jobs(data_dir)
    ds, task, units, ids = _units(data_dir)
    folder = _root(data_dir)
    _completed_record(folder / BASELINE_RESULTS, task, ids, ds.fingerprint)

    output = folder / CANDIDATE_RESULTS
    if output.exists():
        raise ValueError(
            "Ya existe una salida holdout V2.1. No duplicar facturación "
            "ni repetir una tarea parcialmente ejecutada."
        )
    if (folder / CANDIDATE_CHECKPOINTS).exists():
        raise ValueError(
            "Existen checkpoints holdout V2.1 sin resultado. "
            "Auditar el estado antes de reanudar."
        )

    lock = folder / "holdout_v21.lock"
    fd = None
    try:
        fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        os.write(fd, str(os.getpid()).encode("ascii"))
        os.close(fd)
        fd = None
        print(
            f"HOLDOUT V2.1: {TARGET_TASK_ID}, {len(units)} unidades, "
            f"{task['model']}. Límite BLANDO USD {budget:.4f}.",
            flush=True,
        )
        try:
            result = await run_orchestrated_trial(
                units,
                task=task,
                dataset_fingerprint=ds.fingerprint,
                context_cache=folder / CANDIDATE_RAG,
                checkpoint_path=folder / CANDIDATE_CHECKPOINTS,
            )
        except Exception as error:
            result = {
                "task_id": task["task_id"],
                "combination_id": task["combination_id"],
                "treatment": task["treatment"],
                "model": task["model"],
                "repetition": task["repetition"],
                "document_id": task["document_id"],
                "dataset_fingerprint": ds.fingerprint,
                "status": "execution_error",
                "unit_results": [],
                "llm_metrics": [],
                "error_type": type(error).__name__,
                "error": str(error)[:1500],
                "reported_cost_incomplete": True,
            }
        result["validation_profile"] = "v21_holdout_tos02"
        result["holdout_manifest_fingerprint"] = frozen["fingerprint"]
        append_jsonl(output, result)
        print(
            f"Estado: {result['status']} | Costo reportado: "
            f"USD {sum_reported_cost(result):.8f}; puede omitir intentos rechazados.",
            flush=True,
        )
        return result
    finally:
        if fd is not None:
            os.close(fd)
        lock.unlink(missing_ok=True)


def _rag_snapshot_map(path: Path) -> dict[str, str]:
    """Audita la igualdad de las evidencias RAG, no sus textos."""
    rows = read_jsonl(path)
    hashes: dict[str, str] = {}
    for row in rows:
        config = row.get("configuration")
        response = row.get("response")
        recorded_sha = row.get("response_sha256")
        if (
            not isinstance(config, dict)
            or not isinstance(response, dict)
            or not isinstance(recorded_sha, str)
            or recorded_sha != canonical_sha256(response)
        ):
            raise ValueError(f"Instantánea RAG no verificable: {path}")
        key = canonical_sha256(config)
        if key in hashes:
            raise ValueError(f"Instantánea RAG duplicada: {path}")
        hashes[key] = recorded_sha
    return hashes


def _exact_mcnemar(discordant_a: int, discordant_b: int) -> float:
    """Valor p bilateral exacto para resultados binarios correctos/erróneos."""
    n = discordant_a + discordant_b
    if n == 0:
        return 1.0
    tail = sum(
        math.comb(n, i) for i in range(min(discordant_a, discordant_b) + 1)
    ) / (2 ** n)
    return min(1.0, 2 * tail)


def compare_holdout(data_dir: Path) -> dict[str, Any]:
    frozen = verify_holdout(data_dir)
    ds, task, units, ids = _units(data_dir)
    folder = _root(data_dir)
    baseline = _completed_record(
        folder / BASELINE_RESULTS, task, ids, ds.fingerprint
    )
    candidate = _completed_record(
        folder / CANDIDATE_RESULTS, task, ids, ds.fingerprint
    )
    if candidate.get("holdout_manifest_fingerprint") != frozen["fingerprint"]:
        raise ValueError("La candidata se ejecutó con otro manifiesto holdout.")
    old_metrics = next(
        item for item in score_campaign_documents(ds, [baseline])
        if item["task_id"] == TARGET_TASK_ID
    )
    new_metrics = next(
        item for item in score_campaign_documents(ds, [candidate])
        if item["task_id"] == TARGET_TASK_ID
    )
    old_pred = {entry["id"]: entry["prediction"] for entry in baseline["unit_results"]}
    new_pred = {entry["id"]: entry["prediction"] for entry in candidate["unit_results"]}

    def core(row):
        matrix = row["binary_confusion_matrix_on_observed"]
        return {
            "accuracy": row["accuracy_evaluable_observed"],
            "f1_macro": row["f1_macro_evaluable_observed"],
            "false_positives": matrix[NPA][PA],
            "false_negatives": matrix[PA][NPA],
            "true_positives": matrix[PA][PA],
            "true_negatives": matrix[NPA][NPA],
            "npa_f1": row["binary_per_class_on_observed"][NPA]["f1"],
            "pa_f1": row["binary_per_class_on_observed"][PA]["f1"],
            "pa_recall": row["binary_per_class_on_observed"][PA]["recall"],
            "duration_ms_reported": row["duration_ms_reported"],
            "cost_usd_reported": row["cost_usd_reported"],
            "cost_reporting_incomplete_attempts":
                row["cost_reporting_incomplete_attempts"],
        }

    old, new = core(old_metrics), core(new_metrics)
    na_ids = [u.technical_id for u in units if u.label == "not_applicable"]
    old_na = sum(old_pred[k] == "not_applicable" for k in na_ids)
    new_na = sum(new_pred[k] == "not_applicable" for k in na_ids)
    elig = [u for u in units if u.label != "not_applicable"]
    a_correct_only = sum(
        old_pred[u.technical_id] == u.label
        and new_pred[u.technical_id] != u.label
        for u in elig
    )
    b_correct_only = sum(
        new_pred[u.technical_id] == u.label
        and old_pred[u.technical_id] != u.label
        for u in elig
    )
    baseline_rag = _rag_snapshot_map(
        folder / "v2_baseline/legal_context_snapshots.jsonl"
    )
    candidate_rag = _rag_snapshot_map(folder / CANDIDATE_RAG)
    rag_equal = (
        len(baseline_rag) == len(candidate_rag) == len(units)
        and baseline_rag == candidate_rag
    )
    delta_f1 = round(new["f1_macro"] - old["f1_macro"], 6)
    passes = (
        delta_f1 >= PREDEFINED_GATE["f1_macro_minimum_delta"]
        and new["false_negatives"] <= old["false_negatives"]
        and new_na >= old_na
        and rag_equal
    )
    result = {
        "comparison": "PREREGISTERED_SINGLE_DOCUMENT_HOLDOUT",
        "interpretation": "exploratory evidence; not full-corpus confirmation",
        "pre_registered_manifest": frozen["fingerprint"],
        "task_id": TARGET_TASK_ID,
        "dataset_fingerprint": ds.fingerprint,
        "units_total": len(units),
        "units_binary_evaluable": len(elig),
        "v2_execution_id": baseline.get("execution_id"),
        "v21_execution_id": candidate.get("execution_id"),
        "v2": old,
        "v21": new,
        "deltas": {
            "accuracy": round(new["accuracy"] - old["accuracy"], 6),
            "f1_macro": delta_f1,
            "false_positives": new["false_positives"] - old["false_positives"],
            "false_negatives": new["false_negatives"] - old["false_negatives"],
            "cost_usd_reported": round(
                new["cost_usd_reported"] - old["cost_usd_reported"], 8
            ),
        },
        "applicability": {
            "not_applicable_reference": len(na_ids),
            "v2_correct": old_na,
            "v21_correct": new_na,
        },
        "paired_accuracy_test": {
            "v2_only_correct": a_correct_only,
            "v21_only_correct": b_correct_only,
            "exact_mcnemar_p_two_sided": _exact_mcnemar(
                a_correct_only, b_correct_only
            ),
            "caution": "Low power for a single document; p-value is descriptive.",
        },
        "changed_unit_predictions": [
            {
                "id": u.technical_id,
                "reference": u.label,
                "v2": old_pred[u.technical_id],
                "v21": new_pred[u.technical_id],
            }
            for u in units
            if old_pred[u.technical_id] != new_pred[u.technical_id]
        ],
        "rag_context_control": {
            "baseline_distinct_queries": len(baseline_rag),
            "v21_distinct_queries": len(candidate_rag),
            "exact_response_sha_equivalent": rag_equal,
            "mismatched_query_hashes": sorted(
                key for key in set(baseline_rag) | set(candidate_rag)
                if baseline_rag.get(key) != candidate_rag.get(key)
            ),
        },
        "passes_preregistered_gate": passes,
        "limitations": [
            "40 units from one previously unevaluated SaaS ToS; not ten documents.",
            "Holded used to tune V2.1; OpenAI chosen as untouched validation set.",
            "Temperature zero does not guarantee deterministic provider execution.",
            "Reported costs can omit invalid paid generations; reconcile Langfuse.",
            "Additional protocol changes require a different version and evidence.",
        ],
    }
    out = folder / "comparison.json"
    if out.exists():
        existing = _load_object(out)
        if existing != result:
            raise ValueError("La comparación guardada difiere; no sobrescribir.")
    else:
        with out.open("x", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
            f.write("\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--verify", action="store_true")
    mode.add_argument("--execute-candidate", action="store_true")
    mode.add_argument("--compare", action="store_true")
    parser.add_argument(
        "--data-dir", type=Path,
        default=Path(os.getenv("EXPERIMENT_DATA_DIR", "data/evaluation")),
    )
    parser.add_argument("--confirm-paid-run", action="store_true")
    parser.add_argument("--max-reported-cost-usd", type=float)
    args = parser.parse_args()
    root = args.data_dir.resolve()
    if args.freeze:
        row = freeze_holdout(root)
        print("HOLDOUT CONGELADO, sin OpenRouter:", row["fingerprint"])
    elif args.verify:
        row = verify_holdout(root)
        print("HOLDOUT VERIFICADO, sin OpenRouter:", row["fingerprint"])
    elif args.compare:
        print(json.dumps(compare_holdout(root), ensure_ascii=False, indent=2))
    else:
        if (
            not args.confirm_paid_run
            or os.getenv("V21_HOLDOUT_EXECUTION_ENABLED", "false").lower()
            != "true"
        ):
            parser.error(
                "Requiere --confirm-paid-run y V21_HOLDOUT_EXECUTION_ENABLED=true."
            )
        if (
            args.max_reported_cost_usd is None
            or not math.isfinite(args.max_reported_cost_usd)
            or args.max_reported_cost_usd <= 0
        ):
            parser.error("--max-reported-cost-usd debe ser positivo y finito.")
        if os.getenv("EXPERIMENT_EXECUTION_ENABLED", "false").lower() == "true":
            parser.error("Deshabilitar EXPERIMENT_EXECUTION_ENABLED primero.")
        verify_holdout(root)
        result = asyncio.run(execute_candidate(root, args.max_reported_cost_usd))
        if result["status"] != "success":
            raise SystemExit(
                "Holdout V2.1 incompleto. Auditar antes de reintentar o comparar."
            )
        print("Holdout V2.1 completo; usar --compare, sin inferencia adicional.")


if __name__ == "__main__":
    main()
