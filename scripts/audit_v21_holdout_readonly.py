"""Auditoría post-ejecución, SOLO LECTURA, ET04-R1 (V2 frente a V2.1).

No llama a OpenRouter ni genera inferencias. El preflight puede consultar
Chroma y Ollama en modo lectura; no modifica prompts, manifiestos,
resultados ni checkpoints. Reporta desvíos de aplicabilidad y diferencias
RAG por cláusula sin revelar el texto contractual o jurídico en consola.

Uso:
  python -m scripts.audit_v21_holdout_readonly
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from app.evaluation.binary_groundtruth import load_binary_groundtruth_v2
from app.evaluation.campaign import document_units
from app.evaluation.design import make_experimental_plan
from app.evaluation.pilot import canonical_sha256, read_jsonl
from scripts.validate_v21_holdout import (
    BASELINE_RESULTS,
    CANDIDATE_RESULTS,
    CANDIDATE_RAG,
    TARGET_TASK_ID,
    _completed_record,
    _root,
    verify_holdout,
)

NPA = "no potencialmente abusiva"
PA = "potencialmente abusiva"
NA = "not_applicable"
CATEGORIES = (NPA, PA, NA)


def _id_mapping(units) -> dict[str, str]:
    """Misma consulta usada por build_legal_search_query para heading=None."""
    return {
        hashlib.sha256(
            ("Cláusula: " + unit.original_text).encode("utf-8")
        ).hexdigest(): unit.technical_id
        for unit in units
    }


def _read_cache(path: Path) -> dict[str, dict[str, Any]]:
    records = read_jsonl(path)
    if not records:
        raise ValueError(f"No se encontraron snapshots RAG en {path}")
    result: dict[str, dict[str, Any]] = {}
    for row in records:
        config, response = row.get("configuration"), row.get("response")
        if not isinstance(config, dict) or not isinstance(response, dict):
            raise ValueError(f"Snapshot sin configuración o respuesta: {path}")
        query_id = config.get("query_sha256")
        if not isinstance(query_id, str) or not query_id:
            raise ValueError(f"Snapshot sin huella de consulta: {path}")
        if row.get("response_sha256") != canonical_sha256(response):
            raise ValueError(f"Snapshot alterado o inconsistente: {path}")
        if query_id in result:
            raise ValueError(f"Consulta repetida en snapshot RAG: {path}")
        result[query_id] = row
    return result


def _match_signature(row: dict[str, Any]) -> list[dict[str, Any]]:
    """Comparación estructural sin distancia: ¿mismo respaldo documental?"""
    response = row["response"]
    matches = response.get("matches", [])
    if not isinstance(matches, list):
        raise ValueError("Respuesta RAG sin lista válida de coincidencias.")
    return [
        {
            key: match.get(key)
            for key in (
                "chunk_id", "document_id", "checksum", "source_url",
                "title", "jurisdiction", "official_citation", "status",
                "content",
            )
        }
        for match in matches
        if isinstance(match, dict)
    ]


def audit(data_dir: Path) -> dict[str, Any]:
    """Analiza resultados congelados; nunca escribe en el filesystem."""
    frozen = verify_holdout(data_dir)
    ds = load_binary_groundtruth_v2(data_dir / "ground_truth_547.csv")
    task = next(
        t for t in make_experimental_plan(ds)["tasks"]
        if t["task_id"] == TARGET_TASK_ID
    )
    units = document_units(ds, task)
    ids = [u.technical_id for u in units]
    root = _root(data_dir)
    baseline = _completed_record(
        root / BASELINE_RESULTS, task, ids, ds.fingerprint
    )
    candidate = _completed_record(
        root / CANDIDATE_RESULTS, task, ids, ds.fingerprint
    )
    if candidate.get("holdout_manifest_fingerprint") != frozen["fingerprint"]:
        raise ValueError("La ejecución candidata no coincide con el holdout.")

    gold = {u.technical_id: u.label for u in units}
    old = {r["id"]: r["prediction"] for r in baseline["unit_results"]}
    new = {r["id"]: r["prediction"] for r in candidate["unit_results"]}
    matrices: dict[str, dict[str, dict[str, int]]] = {}
    for name, preds in (("v2", old), ("v21", new)):
        grid = {actual: {label: 0 for label in CATEGORIES}
                for actual in CATEGORIES}
        for unit in units:
            predicted = preds[unit.technical_id]
            if predicted not in CATEGORIES:
                raise ValueError("Predicción fuera del esquema.")
            grid[unit.label][predicted] += 1
        matrices[name] = grid

    # Una etiqueta NPA/PA que el modelo declara not_applicable NO entra
    # en las cuatro celdas binarias, pero sí se penaliza como error en F1.
    misapplied = {
        name: [
            {
                "id": unit.technical_id,
                "ground_truth": unit.label,
                "prediction": preds[unit.technical_id],
            }
            for unit in units
            if (unit.label == NA) != (preds[unit.technical_id] == NA)
        ]
        for name, preds in (("v2", old), ("v21", new))
    }

    old_rag = _read_cache(root / "v2_baseline/legal_context_snapshots.jsonl")
    new_rag = _read_cache(root / CANDIDATE_RAG)
    id_by_query = _id_mapping(units)
    differences: list[dict[str, Any]] = []
    for query_sha in sorted(set(old_rag) | set(new_rag)):
        one, two = old_rag.get(query_sha), new_rag.get(query_sha)
        if one is None or two is None:
            differences.append({
                "technical_id": id_by_query.get(query_sha),
                "query_sha256": query_sha,
                "issue": "query_not_present_in_both_versions",
            })
            continue
        if one["configuration"] != two["configuration"]:
            differences.append({
                "technical_id": id_by_query.get(query_sha),
                "query_sha256": query_sha,
                "issue": "configuration_mismatch",
            })
            continue
        if one["response_sha256"] == two["response_sha256"]:
            continue
        matches1 = one["response"].get("matches", [])
        matches2 = two["response"].get("matches", [])
        structure_equal = _match_signature(one) == _match_signature(two)
        same_ordered_ids = (
            [m.get("chunk_id") for m in matches1] ==
            [m.get("chunk_id") for m in matches2]
        )
        differences.append({
            "technical_id": id_by_query.get(query_sha),
            "query_sha256": query_sha,
            "issue": "rag_response_sha_diff",
            "same_ordered_legal_chunks": same_ordered_ids,
            "same_source_and_content_excluding_distance": structure_equal,
            "v2_distance": [
                round(m.get("distance", 0), 6) for m in matches1
            ],
            "v21_distance": [
                round(m.get("distance", 0), 6) for m in matches2
            ],
            "v2_match_count": len(matches1),
            "v21_match_count": len(matches2),
        })

    return {
        "type": "READ_ONLY_POST_HOC_AUDIT",
        "task_id": TARGET_TASK_ID,
        "fingerprint": frozen["fingerprint"],
        "dataset_fingerprint": ds.fingerprint,
        "expected_ids": len(ids),
        "matrix_including_applicability": matrices,
        "applicability_disagreements": misapplied,
        "rag": {
            "v2_snapshot_count": len(old_rag),
            "v21_snapshot_count": len(new_rag),
            "unmatched_query_identity_count": len(
                (set(old_rag) | set(new_rag)) - set(id_by_query)
            ),
            "mismatch_count": len(differences),
            "mismatches": differences,
        },
        "notes": [
            "No modifica preflight ni resultados existentes.",
            "Si los mismos chunks y contenido difieren solo en distance, "
            "las diferencias pueden ser numéricas o de metadatos.",
            "Si cambia el conjunto de fuentes, la comparación mezcla prompt "
            "y recuperación; no atribuir toda diferencia al prompt.",
            "El estado not_applicable en una unidad evaluable afecta "
            "el F1 aunque quede fuera de las cuatro celdas NPA/PA.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir", type=Path, default=Path("data/evaluation")
    )
    args = parser.parse_args()
    print(json.dumps(
        audit(args.data_dir.resolve()), indent=2, ensure_ascii=False
    ))


if __name__ == "__main__":
    main()
