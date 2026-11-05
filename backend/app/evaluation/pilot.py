"""Piloto de inferencia con contexto RAG congelado, sin acceso a etiquetas humanas."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

from app.agents.knowledge_agent import run_knowledge_agent
from app.agents.legal_analyzer_agent import (
    LEGAL_CONTEXT_RESULTS,
    build_legal_search_query,
)
from app.core.config import settings
from app.evaluation.groundtruth import GroundTruthUnit
from app.llm.models import ModelProviderError
from app.llm.openrouter_client import generate_with_openrouter
from app.prompts.legal_analysis import (
    build_legal_analysis_messages,
    get_legal_analysis_response_schema,
)
from app.schemas.knowledge import KnowledgeQuery, LegalKnowledgeMatch
from app.schemas.legal_analysis import (
    ClauseAnalysisDecision,
    ClauseAnalysisRequest,
)
from app.schemas.preprocessing import ProcessedClause
from app.services.analysis import (
    ClassificationExecution,
    build_grounded_assessment,
)

MODEL_LABELS = {
    "not_potentially_abusive": "no potencialmente abusiva",
    "potentially_abusive": "potencialmente abusiva",
}


def canonical_sha256(value: object) -> str:
    """Huella del contenido JSON semánticamente estable."""
    serialized = json.dumps(
        value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def make_request(unit: GroundTruthUnit) -> ClauseAnalysisRequest:
    """Proyección sin etiqueta. URL es un marcador técnico, NO fuente real."""
    data = unit.model_input()
    document_id, position = data["id"].split("-U")
    language = "es" if document_id in {"ToS01", "ToS02"} else "en"
    return ClauseAnalysisRequest(
        source_url=f"https://evaluation.invalid/tos/{document_id}",
        platform=data["platform"],
        language=language,
        clause=ProcessedClause(
            order=int(position),
            original_order=int(position),
            content=data["text"],
        ),
    )


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Carga resultados existentes, rechazando líneas corruptas."""
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for position, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            parsed = json.loads(line)
            if not isinstance(parsed, dict):
                raise ValueError(
                    f"{path}, línea {position}: se esperaba un objeto."
                )
            records.append(parsed)
    return records


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    """Apéndice durable de resultados: nunca sobrescribe ejecuciones."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        handle.flush()


def context_settings() -> dict[str, object]:
    return {
        "embedding_model": settings.ollama_embedding_model,
        "embedding_dimensions": settings.ollama_embedding_dimensions,
        "chroma_collection": settings.chroma_collection,
        "top_k": LEGAL_CONTEXT_RESULTS,
    }


def load_or_retrieve_context(
    unit: GroundTruthUnit,
    request: ClauseAnalysisRequest,
    snapshot_path: Path,
) -> tuple[list[LegalKnowledgeMatch], str, bool, float]:
    """Recupera una vez y fija la evidencia para todas las variantes LLM.

    Un error del agente jurídico NO se convierte silenciosamente en
    contexto vacío. La instantánea se guarda fuera de Git.
    """
    config = context_settings()
    for row in read_jsonl(snapshot_path):
        if (
            row.get("id") == unit.technical_id
            and row.get("text_sha256") == unit.text_sha256
            and row.get("retrieval_config") == config
        ):
            data = row["matches"]
            actual_hash = canonical_sha256(data)
            if row.get("context_sha256") != actual_hash:
                raise ValueError(
                    "La instantánea RAG no supera el control SHA-256."
                )
            return (
                [LegalKnowledgeMatch.model_validate(item) for item in data],
                actual_hash, True, 0.0,
            )

    started = perf_counter()
    knowledge_response = run_knowledge_agent(
        KnowledgeQuery(
            query=build_legal_search_query(request),
            top_k=LEGAL_CONTEXT_RESULTS,
        )
    )
    elapsed = perf_counter() - started
    if knowledge_response.status != "success":
        raise RuntimeError(
            knowledge_response.error
            or "El agente jurídico no pudo recuperar contexto RAG."
        )

    matches = knowledge_response.matches
    serialized = [
        item.model_dump(mode="json") for item in matches
    ]
    digest = canonical_sha256(serialized)
    append_jsonl(snapshot_path, {
        "id": unit.technical_id,
        "text_sha256": unit.text_sha256,
        "retrieval_config": config,
        "context_sha256": digest,
        "matches": serialized,
        "retrieved_at": datetime.now(UTC).isoformat(),
    })
    return matches, digest, False, round(elapsed, 4)


def already_completed(
    rows: list[dict[str, Any]],
    *,
    task_id: str,
    technical_id: str,
    fingerprint: str,
    retry_errors: bool = False,
) -> bool:
    """La reanudación no genera predicciones duplicadas tras éxito."""
    attempts = [
        r for r in rows
        if r.get("task_id") == task_id
        and r.get("id") == technical_id
        and r.get("dataset_fingerprint") == fingerprint
    ]
    if any(r.get("status") == "success" for r in attempts):
        return True
    return bool(attempts) and not retry_errors


def predict_one(
    unit: GroundTruthUnit,
    task: dict[str, object],
    fingerprint: str,
    context_path: Path,
    *,
    infer=generate_with_openrouter,
) -> dict[str, Any]:
    """Hace UNA llamada; conserva respuesta cruda y trazabilidad.

    No se consulta unit.label ni unit.applicability; solo model_input,
    ID y hash del original. Las métricas se calculan en otro proceso.
    """
    request = make_request(unit)
    trace_id = uuid4().hex
    record: dict[str, Any] = {
        "id": unit.technical_id,
        "document_id": task["document_id"],
        "task_id": task["task_id"],
        "combination_id": task["combination_id"],
        "repetition": task["repetition"],
        "treatment": task["treatment"],
        "model": task["model"],
        "dataset_fingerprint": fingerprint,
        "text_sha256": unit.text_sha256,
        "trace_id": trace_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "status": "error",
        "prediction": None,
        "returned_model": None,
        "source_url_is_placeholder": True,
        "rag_context_sha256": None,
        "rag_count": None,
        "rag_from_snapshot": None,
        "rag_seconds": None,
        "prompt_sha256": None,
        "inference_seconds": None,
        "prompt_tokens": None,
        "completion_tokens": None,
        "cost_usd": None,
        "decision": None,
        "raw_response": None,
        "error_type": None,
        "error": None,
    }

    try:
        matches, context_hash, reused, rag_seconds = (
            load_or_retrieve_context(unit, request, context_path)
        )
        record.update({
            "rag_context_sha256": context_hash,
            "rag_count": len(matches),
            "rag_from_snapshot": reused,
            "rag_seconds": rag_seconds,
        })
        messages = build_legal_analysis_messages(request, matches)
        schema = get_legal_analysis_response_schema()
        record["prompt_sha256"] = canonical_sha256({
            "messages": [message.model_dump() for message in messages],
            "schema": schema,
        })

        began = perf_counter()
        try:
            model_result = infer(
                messages,
                schema,
                trace_context={"trace_id": trace_id},
                model=str(task["model"]),
            )
        finally:
            record["inference_seconds"] = round(
                perf_counter() - began, 4
            )
        record.update({
            "returned_model": model_result.model,
            "prompt_tokens": model_result.prompt_tokens,
            "completion_tokens": model_result.completion_tokens,
            "cost_usd": model_result.cost_usd,
            "raw_response": model_result.content,
        })

        decision = ClauseAnalysisDecision.model_validate_json(
            model_result.content
        )
        # Aplica la misma verificación de fundamentos que el
        # servicio ordinario de clasificación.
        build_grounded_assessment(
            ClassificationExecution(
                decision=decision,
                model_response=model_result,
            ),
            request,
            matches,
        )
        predicted = (
            "not_applicable"
            if decision.analysis_status == "not_applicable"
            else MODEL_LABELS[decision.classification]
        )
        record["prediction"] = predicted
        record["decision"] = decision.model_dump(mode="json")
        record["status"] = "success"

    except Exception as error:  # El error debe quedar visible y medirse.
        record["error_type"] = type(error).__name__
        record["error"] = str(error)[:1200]
        record["status"] = (
            "provider_error" if isinstance(error, ModelProviderError)
            else "invalid_or_runtime_error"
        )

    return record
