"""Campaña LangGraph/MCP: 90 tareas documentales, sin ejecución implícita.

Cada tarea procesa todo el documento en UN grafo y produce un informe.
--max-reported-cost-usd es un freno BLANDO entre documentos, no un límite
duro del gasto de una tarea en curso.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.evaluation.campaign import (
    completed_document_run, document_units, run_classification,
    sum_reported_cost, task_progress,
)
from app.evaluation.design import make_experimental_plan
from app.evaluation.groundtruth import load_groundtruth_csv
from app.evaluation.orchestrated import run_orchestrated_trial
from app.evaluation.pilot import append_jsonl, read_jsonl

FROZEN_FINGERPRINT = (
    "47f69eb943f539751f2c120ab6fdd7f45bbc000f93459a90f1162212cfdde4a5"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Planifica o ejecuta tareas documentales por LangGraph/MCP."
    )
    parser.add_argument("--csv", type=Path, required=True)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--task-id", help="Ej. ET01-R2")
    selection.add_argument("--all", action="store_true")
    parser.add_argument("--max-tasks", type=int, default=1)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-full-document", action="store_true")
    parser.add_argument("--retry-errors", action="store_true")
    parser.add_argument("--max-reported-cost-usd", type=float)
    parser.add_argument(
        "--output", type=Path,
        default=Path("data/evaluation/formal_campaign_runs.jsonl"),
    )
    parser.add_argument(
        "--context-cache", type=Path,
        default=Path("data/evaluation/formal_legal_context_snapshots.jsonl"),
    )
    args = parser.parse_args()
    if not 1 <= args.max_tasks <= 5:
        parser.error("--max-tasks debe estar entre 1 y 5.")
    if args.max_reported_cost_usd is not None and (
        not math.isfinite(args.max_reported_cost_usd)
        or args.max_reported_cost_usd <= 0
    ):
        parser.error("--max-reported-cost-usd debe ser positivo y finito.")
    if args.execute and (
        not args.confirm_full_document
        or args.max_reported_cost_usd is None
    ):
        parser.error(
            "Para facturar debes incluir --confirm-full-document y "
            "--max-reported-cost-usd. Este último es un límite BLANDO "
            "entre tareas, no un límite de facturación duro."
        )
    return args


def select_tasks(
    tasks: list[dict[str, Any]],
    task_id: str | None,
) -> list[dict[str, Any]]:
    if task_id is None:
        return tasks
    chosen = [task for task in tasks if task["task_id"] == task_id]
    if len(chosen) != 1:
        raise ValueError(f"Tarea desconocida: {task_id}")
    return chosen


async def execute_tasks(args, dataset, tasks, prior):
    reported_spend = 0.0
    launched = 0
    for task in tasks:
        if launched >= args.max_tasks:
            break
        if reported_spend >= args.max_reported_cost_usd:
            print("Límite blando alcanzado. No se inicia otra tarea.")
            break

        units = document_units(dataset, task)
        ids = [unit.technical_id for unit in units]
        status = run_classification(prior, task, ids, dataset.fingerprint)
        if status == "completed":
            continue
        if status == "failed" and not args.retry_errors:
            print(f"{task['task_id']}: fallo previo; requiere --retry-errors.")
            continue

        launched += 1
        print(
            f"Ejecutando {task['task_id']} | {task['document_id']} | "
            f"{task['model']} | {len(units)} unidades.",
            flush=True,
        )
        try:
            result = await run_orchestrated_trial(
                units,
                task=task,
                dataset_fingerprint=dataset.fingerprint,
                context_cache=args.context_cache,
            )
        except Exception as error:
            # Nunca inventar resultados ni costo ante una excepción.
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
        append_jsonl(args.output, result)
        prior.append(result)
        reported_spend += sum_reported_cost(result)
        state = run_classification(prior, task, ids, dataset.fingerprint)
        print(
            f"{task['task_id']}: estado={state}, "
            f"costo reportado acumulado USD {reported_spend:.6f}",
            flush=True,
        )
        if state != "completed":
            print("Se detuvo por tarea fallida. Revisar salida JSONL.")
            break

    print(json.dumps(
        task_progress(
            dataset, make_experimental_plan(dataset)["tasks"], prior
        ),
        indent=2, ensure_ascii=False,
    ))


def main() -> None:
    args = parse_args()
    dataset = load_groundtruth_csv(args.csv)
    if dataset.fingerprint != FROZEN_FINGERPRINT:
        raise SystemExit("Huella de ground truth diferente: se cancela.")
    plan = make_experimental_plan(dataset)
    all_tasks = plan["tasks"]
    selected = select_tasks(all_tasks, args.task_id)
    prior = read_jsonl(args.output)

    print(json.dumps(
        task_progress(dataset, all_tasks, prior),
        indent=2, ensure_ascii=False,
    ))
    pending = []
    for task in selected:
        ids = [unit.technical_id for unit in document_units(dataset, task)]
        state = run_classification(prior, task, ids, dataset.fingerprint)
        if state == "completed" or (
            state == "failed" and not args.retry_errors
        ):
            continue
        pending.append(task)

    if not args.execute:
        for task in pending[:args.max_tasks]:
            print(
                f"VISTA PREVIA: {task['task_id']} | {task['model']} | "
                f"{task['unit_count']} unidades | R{task['repetition']}"
            )
        if not pending:
            print("No hay tareas elegibles en esta selección.")
        print("No se consultaron MCP, RAG ni OpenRouter.")
        return

    if not settings.openrouter_api_key.get_secret_value().strip():
        raise SystemExit("Falta OPENROUTER_API_KEY.")
    if not pending:
        print("No hay tareas pendientes.")
        return

    lock = args.output.with_suffix(args.output.suffix + ".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        handle = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise SystemExit(
            f"Existe bloqueo {lock}; comprobar proceso activo antes de "
            "retirarlo."
        ) from error
    try:
        os.write(handle, str(os.getpid()).encode("ascii"))
        os.close(handle)
        # Una sola campaña por archivo de salida (bloqueo exclusivo).
        fresh = read_jsonl(args.output)
        asyncio.run(execute_tasks(args, dataset, pending, fresh))
    finally:
        lock.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
