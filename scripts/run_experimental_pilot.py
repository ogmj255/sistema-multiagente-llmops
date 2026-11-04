"""Piloto controlado de una tarea; --execute autoriza llamadas de pago."""

from __future__ import annotations

import argparse
from pathlib import Path

from app.core.config import settings
from app.evaluation.design import make_experimental_plan
from app.evaluation.groundtruth import load_groundtruth_csv
from app.evaluation.pilot import (
    already_completed,
    append_jsonl,
    predict_one,
    read_jsonl,
)

# Versión validada por el investigador en VS Code el 04/11/2026.
PINNED_FINGERPRINT = (
    "47f69eb943f539751f2c120ab6fdd7f45bbc000f93459a90f1162212cfdde4a5"
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Piloto de un tratamiento y repetición con RAG congelado."
    )
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--unit-id")
    parser.add_argument("--limit", type=int, default=1)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--retry-errors", action="store_true")
    parser.add_argument(
        "--output", type=Path,
        default=Path("data/evaluation/pilot_predictions.jsonl"),
    )
    parser.add_argument(
        "--context-cache", type=Path,
        default=Path("data/evaluation/legal_context_snapshots.jsonl"),
    )
    args = parser.parse_args()

    if not 1 <= args.limit <= 5:
        parser.error("El piloto permite --limit entre 1 y 5.")
    groundtruth = load_groundtruth_csv(args.csv)
    if groundtruth.fingerprint != PINNED_FINGERPRINT:
        parser.error(
            "Huella del ground truth distinta de la versión validada: "
            f"{groundtruth.fingerprint}. No se realizará inferencia."
        )

    plan = make_experimental_plan(groundtruth)
    tasks = [
        task for task in plan["tasks"] if task["task_id"] == args.task_id
    ]
    if len(tasks) != 1:
        parser.error("ID de tarea no reconocido. Consulta el plan de 90 tareas.")
    task = tasks[0]

    candidates = [
        unit for unit in groundtruth.units
        if unit.technical_id.startswith(task["document_id"] + "-U")
    ]
    if args.unit_id:
        candidates = [
            unit for unit in candidates
            if unit.technical_id == args.unit_id
        ]
        if not candidates:
            parser.error(
                "La unidad indicada no pertenece al documento de la tarea."
            )
    candidates = candidates[:args.limit]
    print(
        f"Tarea {task['task_id']} | {task['model']} | "
        f"{len(candidates)} unidad(es) | SHA {groundtruth.fingerprint}"
    )

    if not args.execute:
        print(
            "Vista previa: NO se consultó RAG ni OpenRouter. "
            "Agrega --execute para autorizar inferencias con costo."
        )
        return

    if not settings.openrouter_api_key.get_secret_value().strip():
        parser.error("Falta OPENROUTER_API_KEY en backend/.env.")

    prior = read_jsonl(args.output)
    successful = failed = skipped = 0
    for index, unit in enumerate(candidates, start=1):
        if already_completed(
            prior,
            task_id=str(task["task_id"]),
            technical_id=unit.technical_id,
            fingerprint=groundtruth.fingerprint,
            retry_errors=args.retry_errors,
        ):
            skipped += 1
            print(f"[{index}/{len(candidates)}] {unit.technical_id}: omitida")
            continue

        record = predict_one(
            unit, task, groundtruth.fingerprint, args.context_cache,
        )
        append_jsonl(args.output, record)
        prior.append(record)
        if record["status"] == "success":
            successful += 1
        else:
            failed += 1
        print(
            f"[{index}/{len(candidates)}] {unit.technical_id} "
            f"status={record['status']} "
            f"latencia={record['inference_seconds']}"
        )
        if record["status"] != "success":
            print("  error:", record["error"])

    print(
        f"Piloto terminado. Éxitos={successful}, errores={failed}, "
        f"omitidos={skipped}. Registro: {args.output}"
    )


if __name__ == "__main__":
    main()
