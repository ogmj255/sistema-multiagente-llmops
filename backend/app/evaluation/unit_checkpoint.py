"""Checkpoint durable POR UNIDAD para tareas documentales de LangGraph.

Solo se reutilizan análisis exitosos del mismo fragmento, tratamiento,
repetición, dataset y configuración. Nunca contiene etiquetas humanas.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from app.core.config import settings
from app.evaluation.groundtruth import GroundTruthUnit
from app.evaluation.pilot import canonical_sha256, read_jsonl
from app.prompts.legal_analysis import (
    SYSTEM_PROMPT,
    get_legal_analysis_response_schema,
)
from app.schemas.legal_analysis import ClauseAnalysisResponse
from app.schemas.observability import LLMInvocationMetrics

CHECKPOINT_VERSION = 1


def analysis_config_sha256() -> str:
    """Congela el prompt, esquema, temperatura y parámetros básicos RAG.

    La revisión del repositorio y la versión del corpus jurídico también
    deben congelarse y documentarse externamente antes de la campaña formal.
    """
    return canonical_sha256({
        "checkpoint_version": CHECKPOINT_VERSION,
        "system_prompt": SYSTEM_PROMPT,
        "output_schema": get_legal_analysis_response_schema(),
        "llm_temperature": settings.llm_temperature,
        "embedding_model": settings.ollama_embedding_model,
        "embedding_dimensions": settings.ollama_embedding_dimensions,
        "chroma_collection": settings.chroma_collection,
        "legal_top_k": 5,
    })


@dataclass(frozen=True)
class RecoveredUnit:
    response: ClauseAnalysisResponse
    metrics: tuple[LLMInvocationMetrics, ...]
    record: dict[str, Any]


class UnitCheckpointStore:
    """Apéndice con fsync: un registro por intento terminado de cláusula.

    Si el proceso se interrumpe durante una solicitud, no se sabe si el
    proveedor la cobró: la recuperación evita duplicar SOLO los éxitos
    persistidos. No garantiza facturación exactamente una vez.
    """

    def __init__(
        self,
        path: Path,
        *,
        task: Mapping[str, object],
        fingerprint: str,
        units: Sequence[GroundTruthUnit],
        configuration_sha256: str | None = None,
    ) -> None:
        self.path = path
        self.task_id = str(task["task_id"])
        self.model = str(task["model"])
        self.repetition = int(task["repetition"])
        self.fingerprint = fingerprint
        self.configuration_sha256 = (
            configuration_sha256 or analysis_config_sha256()
        )
        self._units = {unit.technical_id: unit for unit in units}
        self._completed: dict[str, RecoveredUnit] = {}
        self._failed: dict[str, dict[str, Any]] = {}
        self._load()

    def _matching(self, row: Mapping[str, Any]) -> bool:
        return (
            row.get("task_id") == self.task_id
            and row.get("id") in self._units
        )

    def _load(self) -> None:
        for row in read_jsonl(self.path):
            if not self._matching(row):
                continue
            technical_id = str(row["id"])
            unit = self._units[technical_id]
            expected = {
                "model": self.model,
                "repetition": self.repetition,
                "dataset_fingerprint": self.fingerprint,
                "text_sha256": unit.text_sha256,
                "analysis_config_sha256": self.configuration_sha256,
            }
            if any(row.get(key) != value for key, value in expected.items()):
                raise ValueError(
                    f"Checkpoint incompatible para {self.task_id} / "
                    f"{technical_id}; no se reutilizará una predicción "
                    "con diferente dataset o configuración."
                )
            self._register(row)

    def _register(self, row: dict[str, Any]) -> None:
        technical_id = str(row["id"])
        if row.get("status") != "success":
            self._failed[technical_id] = row
            return
        response = ClauseAnalysisResponse.model_validate(row.get("response"))
        if response.status != "success":
            raise ValueError(
                f"Checkpoint incoherente: {technical_id} no tiene respuesta exitosa."
            )
        metrics = tuple(
            LLMInvocationMetrics.model_validate(value)
            for value in row.get("llm_metrics", [])
        )
        self._completed[technical_id] = RecoveredUnit(
            response=response,
            metrics=metrics,
            record=row,
        )

    def lookup(self, unit_id: str) -> RecoveredUnit | None:
        return self._completed.get(unit_id)

    def counts(self) -> dict[str, int]:
        return {
            "successful_checkpoint_units": len(self._completed),
            "failed_checkpoint_units": len(
                set(self._failed) - set(self._completed)
            ),
        }

    def record(
        self,
        unit: GroundTruthUnit,
        *,
        response: ClauseAnalysisResponse,
        metrics: Sequence[LLMInvocationMetrics],
        execution_id: str,
    ) -> None:
        """Registra el resultado ANTES de devolverlo al grafo.

        Si la escritura falla, se aborta la ejecución; nunca se presenta
        como checkpoint seguro sin haber hecho flush y fsync.
        """
        if unit.technical_id not in self._units:
            raise ValueError("Unidad ajena a la tarea experimental.")
        if self.lookup(unit.technical_id) is not None:
            raise ValueError(
                f"{unit.technical_id}: éxito previo, no debe duplicarse."
            )
        row: dict[str, Any] = {
            "version": CHECKPOINT_VERSION,
            "task_id": self.task_id,
            "id": unit.technical_id,
            "model": self.model,
            "repetition": self.repetition,
            "dataset_fingerprint": self.fingerprint,
            "text_sha256": unit.text_sha256,
            "analysis_config_sha256": self.configuration_sha256,
            "execution_id": execution_id,
            "recorded_at": datetime.now(UTC).isoformat(),
            "status": response.status,
            "response": response.model_dump(mode="json"),
            "llm_metrics": [
                metric.model_dump(mode="json") for metric in metrics
            ],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as target:
            target.write(json.dumps(row, ensure_ascii=False) + "\n")
            target.flush()
            os.fsync(target.fileno())
        self._register(row)

    def cumulative_success_usage(self) -> dict[str, object]:
        """Tokens/costo por éxitos únicos, también si hubo reanudación."""
        metrics = [
            metric
            for recovered in self._completed.values()
            for metric in recovered.metrics
        ]
        known_costs = [
            metric.cost_usd
            for metric in metrics
            if metric.cost_usd is not None
        ]
        return {
            "successful_units": len(self._completed),
            "prompt_tokens_reported": sum(
                metric.prompt_tokens or 0 for metric in metrics
            ),
            "completion_tokens_reported": sum(
                metric.completion_tokens or 0 for metric in metrics
            ),
            "cost_usd_reported": round(sum(known_costs), 8),
            "missing_cost_records": sum(
                metric.cost_usd is None for metric in metrics
            ),
        }
