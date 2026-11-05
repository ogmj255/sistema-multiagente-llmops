"""Checkpoint por unidad: integridad, idempotencia y costos sin API."""

import json

import pytest

from app.evaluation.groundtruth import GroundTruthUnit
from app.evaluation.unit_checkpoint import UnitCheckpointStore
from app.schemas.legal_analysis import ClauseAnalysisResponse, ClauseAssessment
from app.schemas.observability import LLMInvocationMetrics


TASK = {
    "task_id": "ET01-R2",
    "model": "deepseek/deepseek-v4-flash-0731",
    "repetition": 2,
}


def unit():
    return GroundTruthUnit(
        technical_id="ToS01-U001",
        platform="Holded",
        original_text="El proveedor puede actualizar el contrato.",
        applicability="Evaluable",
        label="ETIQUETA_HUMANA_SECRETA",
        text_sha256="1" * 64,
    )


def response():
    return ClauseAnalysisResponse(
        status="success",
        result=ClauseAssessment(
            category="Modificación",
            clause_type="Facultad unilateral",
            target="usuario",
            classification="potentially_abusive",
            analysis_status="classified",
            relevant_fragment=unit().original_text,
            justification="Podría existir un desequilibrio.",
            evidence_sufficiency="insufficient",
            legal_basis=[],
        ),
    )


def make_store(path, **kwargs):
    return UnitCheckpointStore(
        path,
        task=kwargs.get("task", TASK),
        fingerprint=kwargs.get("fingerprint", "f" * 64),
        units=kwargs.get("units", [unit()]),
        configuration_sha256=kwargs.get("config", "c" * 64),
    )


def test_checkpoint_is_durable_replayable_and_has_no_label(tmp_path):
    path = tmp_path / "unit_checkpoint.jsonl"
    store = make_store(path)
    metric = LLMInvocationMetrics(
        provider="openrouter",
        model=TASK["model"],
        prompt_tokens=20,
        completion_tokens=10,
        total_tokens=30,
        cost_usd=0.01,
    )
    store.record(
        unit(), response=response(), metrics=[metric],
        execution_id="run-001",
    )
    text = path.read_text(encoding="utf-8")
    assert "ETIQUETA_HUMANA_SECRETA" not in text
    assert json.loads(text)["status"] == "success"

    recovered = make_store(path)
    previous = recovered.lookup("ToS01-U001")
    assert previous is not None
    assert previous.response.result.classification == "potentially_abusive"
    assert recovered.cumulative_success_usage() == {
        "successful_units": 1,
        "prompt_tokens_reported": 20,
        "completion_tokens_reported": 10,
        "cost_usd_reported": 0.01,
        "missing_cost_records": 0,
    }
    with pytest.raises(ValueError, match="no debe duplicarse"):
        recovered.record(
            unit(), response=response(), metrics=[metric],
            execution_id="run-002",
        )


def test_checkpoint_rejects_conflicting_configuration_or_text(tmp_path):
    path = tmp_path / "unit_checkpoint.jsonl"
    make_store(path).record(
        unit(), response=response(), metrics=[],
        execution_id="run-001",
    )
    with pytest.raises(ValueError, match="Checkpoint incompatible"):
        make_store(path, config="changed")
    changed = GroundTruthUnit(
        technical_id=unit().technical_id,
        platform=unit().platform,
        original_text="Una cláusula diferente.",
        applicability="Evaluable",
        label="OTRA_ETIQUETA",
        text_sha256="2" * 64,
    )
    with pytest.raises(ValueError, match="Checkpoint incompatible"):
        make_store(path, units=[changed])
    with pytest.raises(ValueError, match="Checkpoint incompatible"):
        make_store(path, fingerprint="a" * 64)


def test_checkpoint_does_not_replay_failure(tmp_path):
    path = tmp_path / "unit_checkpoint.jsonl"
    store = make_store(path)
    store.record(
        unit(),
        response=ClauseAnalysisResponse(
            status="error", error="HTTP 429.",
            error_code="provider_rate_limited",
        ),
        metrics=[],
        execution_id="failed-run",
    )
    reloaded = make_store(path)
    assert reloaded.lookup("ToS01-U001") is None
    assert reloaded.counts()["failed_checkpoint_units"] == 1
    reloaded.record(
        unit(), response=response(), metrics=[],
        execution_id="successful-run",
    )
    finished = make_store(path)
    assert finished.lookup("ToS01-U001") is not None
    assert finished.counts()["failed_checkpoint_units"] == 0


def test_other_repetition_is_not_replayed(tmp_path):
    path = tmp_path / "unit_checkpoint.jsonl"
    make_store(path).record(
        unit(), response=response(), metrics=[],
        execution_id="run-001",
    )
    # Los registros de R2 no se adoptan para R3.
    other = make_store(path, task={**TASK, "task_id": "ET01-R3", "repetition": 3})
    assert other.lookup("ToS01-U001") is None
