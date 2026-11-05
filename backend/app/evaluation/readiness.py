"""Preflight de campaña binaria V2: sin solicitudes a OpenRouter.

Congela una huella de la colección jurídica, configuración de inferencia,
referencia humana V2 y archivos de código críticos. No exporta textos
jurídicos, predicciones ni credenciales.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import numpy as np

from app.core.config import settings
from app.evaluation.binary_groundtruth import (
    binary_manifest, load_binary_groundtruth_v2,
)
from app.evaluation.design import make_experimental_plan
from app.evaluation.pilot import canonical_sha256
from app.evaluation.unit_checkpoint import analysis_config_sha256
from app.services.legal_vector_store import create_chroma_client

PROTOCOL = "NPA-PA-v2.0"
MANIFEST_FILENAME = "v2_binary_preflight_manifest.json"
CRITICAL_SOURCES = (
    "prompts/legal_analysis.py",
    "schemas/legal_analysis.py",
    "agents/orchestrator_agent.py",
    "agents/legal_analyzer_agent.py",
    "evaluation/orchestrated.py",
    "evaluation/unit_checkpoint.py",
    "llm/openrouter_client.py",
    "mcp/registry.py",
)


class PreflightError(RuntimeError):
    """Impide iniciar una campaña que no es reproducible."""


def _code_sha256() -> str:
    app_folder = Path(__file__).resolve().parents[1]
    files = []
    for rel in CRITICAL_SOURCES:
        path = app_folder / rel
        if not path.is_file():
            raise PreflightError(f"Falta código crítico: {rel}")
        files.append({
            "path": rel,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
    worker = Path(__file__).resolve().parents[2] / "scripts" / "evaluation_worker.py"
    if not worker.is_file():
        raise PreflightError("Falta el script del worker experimental.")
    files.append({
        "path": "scripts/evaluation_worker.py",
        "sha256": hashlib.sha256(worker.read_bytes()).hexdigest(),
    })
    return canonical_sha256(files)


def _collection_inventory() -> dict[str, Any]:
    """Consulta Chroma en SOLO LECTURA; no crea colecciones ni vectores."""
    client = create_chroma_client()
    collection = client.get_collection(name=settings.chroma_collection)
    count = collection.count()
    if not isinstance(count, int) or count <= 0:
        raise PreflightError("La colección jurídica está vacía.")

    metadata = collection.metadata or {}
    embedding_model = metadata.get("embedding_model")
    dimensions = metadata.get("embedding_dimensions")
    if embedding_model is not None and embedding_model != settings.ollama_embedding_model:
        raise PreflightError("El modelo de embeddings no coincide con la colección.")
    if dimensions is not None and dimensions != settings.ollama_embedding_dimensions:
        raise PreflightError("Las dimensiones no coinciden con ChromaDB.")

    hashes: list[str] = []
    offset = 0
    while offset < count:
        block = collection.get(
            limit=min(128, count - offset),
            offset=offset,
            include=["documents", "metadatas", "embeddings"],
        )
        ids = block.get("ids", [])
        docs = block.get("documents")
        metas = block.get("metadatas")
        vectors = block.get("embeddings")
        if (
            docs is None or metas is None or vectors is None
            or not ids
            or len(ids) != len(docs)
            or len(ids) != len(metas)
            or len(ids) != len(vectors)
        ):
            raise PreflightError("ChromaDB devolvió un inventario incompleto.")
        for id_, document, metadata_row, embedding in zip(
            ids, docs, metas, vectors, strict=True
        ):
            vector = np.asarray(embedding, dtype=np.float32)
            if vector.ndim != 1 or len(vector) != settings.ollama_embedding_dimensions:
                raise PreflightError("Un vector jurídico tiene dimensiones incorrectas.")
            hashes.append(canonical_sha256({
                "id": id_,
                "document": document,
                "metadata": metadata_row,
                "embedding_sha256": hashlib.sha256(vector.tobytes()).hexdigest(),
            }))
        offset += len(ids)
    if len(hashes) != count or collection.count() != count:
        raise PreflightError("Cambió el número de segmentos durante el inventario.")
    return {
        "collection": settings.chroma_collection,
        "chunks": count,
        "embedding_model": settings.ollama_embedding_model,
        "embedding_dimensions": settings.ollama_embedding_dimensions,
        "collection_sha256": canonical_sha256(sorted(hashes)),
    }


def _check_ollama_model() -> dict[str, str]:
    response = httpx.get(
        f"{settings.ollama_base_url.rstrip('/')}/api/tags",
        timeout=15.0,
    )
    response.raise_for_status()
    available = {
        item.get("name")
        for item in response.json().get("models", [])
        if isinstance(item, dict)
    }
    model = settings.ollama_embedding_model
    if model not in available:
        raise PreflightError(
            "El modelo local de embeddings no está disponible en Ollama."
        )
    return {
        "embedding_model": model,
        "endpoint_checked": True,
    }


def create_readiness_manifest(data_dir: Path) -> dict[str, Any]:
    """Prepara manifest SIN inferencia; exige servicios locales accesibles."""
    dataset = load_binary_groundtruth_v2(
        data_dir / "ground_truth_547.csv"
    )
    plan = make_experimental_plan(dataset)
    if (
        plan["executions"] != 90
        or plan["expected_unit_predictions"] != 4923
    ):
        raise PreflightError("El diseño experimental no coincide con el aprobado.")
    if not settings.openrouter_api_key.get_secret_value().strip():
        raise PreflightError("Falta OPENROUTER_API_KEY.")
    if settings.llm_temperature != 0:
        raise PreflightError(
            "La evaluación controlada requiere temperatura 0."
        )

    legal = _collection_inventory()
    ollama = _check_ollama_model()
    summary = binary_manifest(dataset)
    return {
        "protocol": PROTOCOL,
        "dataset_fingerprint": dataset.fingerprint,
        "source_sha256": dataset.source_sha256,
        "labels": summary["classification_labels"],
        "applicability": summary["applicability"],
        "tasks": plan["executions"],
        "expected_predictions": plan["expected_unit_predictions"],
        "config_sha256": analysis_config_sha256(),
        "code_sha256": _code_sha256(),
        "model_ids": plan["treatments"],
        "llm_temperature": settings.llm_temperature,
        "rag": legal,
        "ollama": ollama,
    }


def verify_readiness(data_dir: Path) -> dict[str, Any]:
    """Revalida el entorno ANTES de cada trabajo facturable."""
    path = data_dir / MANIFEST_FILENAME
    if not path.is_file():
        raise PreflightError(
            "Falta el manifiesto del preflight V2; no se ejecuta OpenRouter."
        )
    try:
        frozen = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PreflightError("El manifiesto V2 no es válido.") from exc
    current = create_readiness_manifest(data_dir)
    if not isinstance(frozen, dict) or frozen.get("fingerprint") != canonical_sha256(current):
        raise PreflightError(
            "La referencia, el código, el prompt o la base RAG cambió "
            "desde el preflight. Se bloquea la ejecución."
        )
    return current


def freeze_readiness(data_dir: Path) -> dict[str, Any]:
    """Congela una única vez y nunca sobrescribe un entorno distinto."""
    result = create_readiness_manifest(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    target = data_dir / MANIFEST_FILENAME
    manifest = {
        "fingerprint": canonical_sha256(result),
        "created_at": datetime.now(UTC).isoformat(),
        "environment": result,
    }
    if target.exists():
        verify_readiness(data_dir)
        return json.loads(target.read_text(encoding="utf-8"))
    temporary = target.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(target)
    return manifest
