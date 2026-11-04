"""Experimento controlado sobre el LangGraph y los servidores MCP reales.

Se reemplazan únicamente los nodos de adquisición/segmentación para
inyectar las unidades congeladas del corpus; análisis, conocimiento jurídico,
informe y observabilidad usan las funciones del orquestador de producción.
No contiene llamadas directas al LLM.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from functools import partial
from pathlib import Path
from time import perf_counter
from typing import Any

from app.agents.observability_agent import build_observability_summary
from app.agents.orchestrator_agent import (
    AgenteOrquestador,
    NodosOrquestacion,
    consolidar_observabilidad,
    distribuir_clausulas,
    finalizar_flujo,
    generar_informe,
    procesar_clausula,
)
from app.core.config import settings
from app.core.observability import (
    start_pipeline_observation,
    update_pipeline_observation,
)
from app.evaluation.groundtruth import GroundTruthUnit
from app.evaluation.pilot import (
    MODEL_LABELS,
    append_jsonl,
    canonical_sha256,
    read_jsonl,
)
from app.mcp.registry import ClienteMCP
from app.schemas.contract import ExtractionRequest
from app.schemas.knowledge import KnowledgeResponse
from app.schemas.orchestration import create_initial_state
from app.schemas.preprocessing import PreprocessedContract, ProcessedClause
from app.services.analysis_persistence import calculate_content_hash


REQUIRED_SERVERS = (
    "conocimiento_juridico",
    "analizador_legal",
    "generador_informes",
    "observabilidad",
)


class FrozenKnowledgeMCP:
    """Proxy MCP: la primera recuperación es real y las siguientes idénticas.

    La clave considera texto completo de consulta, dataset, top_k y ajustes
    de embedding/Chroma. No registra ni recibe etiquetas humanas.
    """

    def __init__(
        self,
        delegate: ClienteMCP,
        *,
        fingerprint: str,
        cache_path: Path,
    ) -> None:
        self._delegate = delegate
        self._fingerprint = fingerprint
        self._cache_path = cache_path
        self.retrieved = 0
        self.reused = 0

    def _configuration(self, arguments: dict[str, object]) -> dict[str, object]:
        return {
            "fingerprint": self._fingerprint,
            "query_sha256": hashlib.sha256(
                str(arguments["query"]).encode("utf-8")
            ).hexdigest(),
            "top_k": arguments["top_k"],
            "embedding_model": settings.ollama_embedding_model,
            "embedding_dimensions": settings.ollama_embedding_dimensions,
            "chroma_collection": settings.chroma_collection,
        }

    async def invocar(
        self,
        key: str,
        arguments: dict[str, object],
    ) -> dict[str, object]:
        if key != "conocimiento_juridico":
            return await self._delegate.invocar(key, arguments)

        config = self._configuration(arguments)
        for row in read_jsonl(self._cache_path):
            if row.get("configuration") != config:
                continue
            response = row.get("response")
            if (
                not isinstance(response, dict)
                or row.get("response_sha256") != canonical_sha256(response)
            ):
                raise ValueError(
                    "La instantánea RAG guardada no supera su SHA-256."
                )
            validated = KnowledgeResponse.model_validate(response)
            if validated.status != "success":
                raise ValueError("La instantánea RAG contiene un error.")
            self.reused += 1
            return response

        response = await self._delegate.invocar(key, arguments)
        validated = KnowledgeResponse.model_validate(response)
        if validated.status == "success":
            append_jsonl(self._cache_path, {
                "configuration": config,
                "response_sha256": canonical_sha256(response),
                "response": response,
            })
            self.retrieved += 1
        return response


def fixed_contract(
    units: Sequence[GroundTruthUnit],
    document_id: str,
    platform: str,
) -> PreprocessedContract:
    """Entrega textos originales, nunca las etiquetas del ground truth."""
    if not units:
        raise ValueError("Se requiere al menos una unidad.")
    if any(
        unit.platform != platform
        or not unit.technical_id.startswith(document_id + "-U")
        for unit in units
    ):
        raise ValueError("Las unidades no corresponden al documento indicado.")

    clauses: list[ProcessedClause] = []
    for unit in units:
        source = unit.model_input()
        ordinal = int(source["id"].split("-U")[1])
        clauses.append(
            ProcessedClause(
                order=ordinal,
                original_order=ordinal,
                content=source["text"],
            )
        )

    clauses.sort(key=lambda clause: clause.order)
    return PreprocessedContract(
        source_url=f"https://evaluation.invalid/tos/{document_id}",
        platform=platform,
        title=f"Evaluación congelada {document_id}",
        language="es" if document_id in {"ToS01", "ToS02"} else "en",
        cleaned_text="\n\n".join(c.content for c in clauses),
        clauses=clauses,
        removed_blocks=[],
    )


def make_fixed_graph(
    client: FrozenKnowledgeMCP,
    contract: PreprocessedContract,
):
    """Reutiliza AgenteOrquestador.construir y los nodos MCP existentes."""

    def supply_extraction(_state):
        # La extracción se evaluará aparte desde URL reales.
        return {"status": "running", "current_step": "preprocessing"}

    def supply_preprocessing(_state):
        # La segmentación se conserva exactamente según el ground truth.
        return {
            "current_step": "knowledge",
            "preprocessed_contract": contract,
        }

    def bypass_production_cache(_state):
        # No reutilizar informes previos de PostgreSQL.
        return {
            "content_hash": calculate_content_hash(contract.cleaned_text),
            "reused_analysis": False,
        }

    nodes = NodosOrquestacion(
        extraer=supply_extraction,
        preprocesar=supply_preprocessing,
        verificar_analisis_previo=bypass_production_cache,
        procesar_clausula=partial(procesar_clausula, cliente=client),
        generar_informe=partial(generar_informe, cliente=client),
        finalizar=finalizar_flujo,
    )
    return AgenteOrquestador(
        nodes,
        distribuir_clausulas,
    ).construir()


async def run_orchestrated_trial(
    units: Sequence[GroundTruthUnit],
    *,
    task: dict[str, object],
    dataset_fingerprint: str,
    context_cache: Path,
) -> dict[str, Any]:
    """Una ejecución LangGraph+MCP sobre cláusulas congeladas.

    No llama directamente a OpenRouter, no toca tablas productivas y
    no cambia la variable de entorno global OPENROUTER_MODEL.
    """
    contract = fixed_contract(
        units,
        str(task["document_id"]),
        str(task["platform"]),
    )
    state = create_initial_state(
        ExtractionRequest(
            url=contract.source_url,
            platform=contract.platform,
        )
    )
    model = str(task["model"])
    started = perf_counter()

    async with ClienteMCP(
        required_servers=REQUIRED_SERVERS,
        environment_overrides={
            "analizador_legal": {"OPENROUTER_MODEL": model},
        },
    ) as actual_client:
        client = FrozenKnowledgeMCP(
            actual_client,
            fingerprint=dataset_fingerprint,
            cache_path=context_cache,
        )
        graph = make_fixed_graph(client, contract)

        with start_pipeline_observation(
            state["execution_id"]
        ) as observation:
            final_state = await graph.ainvoke(
                state,
                config={"max_concurrency": 1},
            )
            duration_ms = (perf_counter() - started) * 1000

            try:
                summary = await consolidar_observabilidad(
                    status=final_state["status"],
                    duration_ms=duration_ms,
                    llm_metrics=final_state["llm_metrics"],
                    error_count=len(final_state["errors"]),
                    cliente=client,
                )
            except RuntimeError:
                summary = build_observability_summary(
                    status=final_state["status"],
                    duration_ms=duration_ms,
                    llm_metrics=final_state["llm_metrics"],
                    error_count=len(final_state["errors"]),
                )

            update_pipeline_observation(
                observation,
                status=final_state["status"],
                reused_analysis=False,
                error_count=len(final_state["errors"]),
            )

    report = final_state["report"]
    responses = final_state["clause_results"]
    per_unit: list[dict[str, object]] = []
    for unit in units:
        order = int(unit.technical_id.split("-U")[1])
        result = responses.get(order)
        if result is None or result.status != "success" or result.result is None:
            per_unit.append({
                "id": unit.technical_id,
                "status": "error",
                "prediction": None,
                "assessment": None,
            })
            continue
        assessment = result.result
        prediction = (
            "not_applicable"
            if assessment.analysis_status == "not_applicable"
            else MODEL_LABELS[assessment.classification]
        )
        per_unit.append({
            "id": unit.technical_id,
            "status": "success",
            "prediction": prediction,
            "assessment": assessment.model_dump(mode="json"),
        })

    metrics = [
        entry.model_dump(mode="json")
        for entry in final_state["llm_metrics"]
    ]
    return {
        "task_id": task["task_id"],
        "combination_id": task["combination_id"],
        "treatment": task["treatment"],
        "model": model,
        "repetition": task["repetition"],
        "document_id": task["document_id"],
        "dataset_fingerprint": dataset_fingerprint,
        "execution_id": final_state["execution_id"],
        "status": final_state["status"],
        "duration_ms": round(duration_ms, 3),
        "rag_retrievals": client.retrieved,
        "rag_reuses": client.reused,
        "llm_metrics": metrics,
        "observability_summary": summary.model_dump(mode="json"),
        "errors": final_state["errors"],
        "unit_results": per_unit,
        "report": report.model_dump(mode="json") if report else None,
        "workflow": {
            "orchestrator": "LangGraph production graph",
            "knowledge": "MCP + frozen RAG snapshot",
            "analysis": "MCP + OpenRouter",
            "report": "MCP report generator",
            "observability": "MCP + Langfuse",
            "scraping": "skipped (frozen contractual units)",
            "preprocessing": "skipped (frozen contractual units)",
            "postgresql": "production cache bypassed; no production writes",
        },
    }
