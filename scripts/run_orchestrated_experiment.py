"""Piloto LangGraph+MCP sobre una unidad del corpus experimental.

El comando solo invoca OpenRouter al recibir --execute. La ruta de
resultados está en data/evaluation/ y no se incluye en Git.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from app.core.config import settings
from app.evaluation.design import make_experimental_plan
from app.evaluation.groundtruth import load_groundtruth_csv
from app.evaluation.orchestrated import run_orchestrated_trial
from app.evaluation.pilot import append_jsonl, read_jsonl

PINNED_FINGERPRINT = (
    "47f69eb943f539751f2c120ab6fdd7f45bbc000f93459a90f1162212cfdde4a5"
)


def completed(
    records: list[dict[str, object]],
    task_id: str,
    unit_id: str,
    fingerprint: str,
) -> bool:
    """No vuelve a pagar una unidad completada con éxito en la misma tarea."""
    return any(
        record.get("task_id") == task_id
        and record.get("dataset_fingerprint") == fingerprint
        and any(
            result.get("id") == unit_id and result.get("status") == "success"
            for result in record.get("unit_results", [])
            if isinstance(result, dict)
        )
        for record in records
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ejecuta un fragmento congelado a través de LangGraph y MCP."
    )
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--unit-id", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--retry-errors", action="store_true")
    parser.add_argument(
        "--results",
        type=Path,
        default=Path("data/evaluation/orchestrated_runs.jsonl"),
    )
    parser.add_argument(
        "--context-cache",
        type=Path,
        default=Path("data/evaluation/mcp_legal_context_snapshots.jsonl"),
    )
    args = parser.parse_args()

    dataset = load_groundtruth_csv(args.csv)
    if dataset.fingerprint != PINNED_FINGERPRINT:
        parser.error(
            "La huella del ground truth no coincide con la versión "
            "fijada. No se realizará ninguna inferencia."
        )

    plan = make_experimental_plan(dataset)
    tasks = [
        item for item in plan["tasks"]
        if item["task_id"] == args.task_id
    ]
    if len(tasks) != 1:
        parser.error("La tarea experimental indicada no existe.")
    task = tasks[0]

    units = [
        item for item in dataset.units
        if item.technical_id == args.unit_id
        and item.technical_id.startswith(task["document_id"] + "-U")
    ]
    if len(units) != 1:
        parser.error("La unidad no pertenece al documento de la tarea.")

    print(
        f"{task['task_id']} | {task['model']} | "
        f"{args.unit_id} | LangGraph+MCP"
    )
    if not args.execute:
        print(
            "Vista previa: no se ejecutaron MCP, RAG ni OpenRouter. "
            "Utiliza --execute solo cuando estés listo para una inferencia real."
        )
        return

    if not settings.openrouter_api_key.get_secret_value().strip():
        parser.error("No está configurada OPENROUTER_API_KEY.")

    prior = read_jsonl(args.results)
    if completed(prior, args.task_id, args.unit_id, dataset.fingerprint):
        print(
            "Esta unidad ya tuvo una ejecución experimental correcta "
            "para la misma tarea. No se repite ni consume créditos."
        )
        return
    if (
        not args.retry_errors
        and any(
            record.get("task_id") == args.task_id
            and record.get("dataset_fingerprint") == dataset.fingerprint
            and any(
                result.get("id") == args.unit_id
                for result in record.get("unit_results", [])
                if isinstance(result, dict)
            )
            for record in prior
        )
    ):
        parser.error(
            "Ya existe un intento de esta tarea. Usa --retry-errors "
            "para reintentar un fallo documentado."
        )

    result = asyncio.run(
        run_orchestrated_trial(
            units,
            task=task,
            dataset_fingerprint=dataset.fingerprint,
            context_cache=args.context_cache,
        )
    )
    append_jsonl(args.results, result)
    prediction = result["unit_results"][0]
    print(json.dumps({
        "status": result["status"],
        "unit_status": prediction["status"],
        "prediction": prediction["prediction"],
        "model": result["model"],
        "task_id": result["task_id"],
        "execution_id": result["execution_id"],
        "duration_ms": result["duration_ms"],
        "rag_retrievals": result["rag_retrievals"],
        "rag_reuses": result["rag_reuses"],
        "llm_metrics": result["llm_metrics"],
        "errors": result["errors"],
    }, ensure_ascii=False, indent=2))
    print(f"Resultados detallados: {args.results}")


if __name__ == "__main__":
    main()
