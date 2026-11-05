"""V2.1 piloto: pruebas sin Chroma, Ollama, MCP ni OpenRouter."""

import copy
import json

import pytest

from app.evaluation.pilot import canonical_sha256
from app.evaluation.readiness import PreflightError
from scripts import validate_prompt_v21 as runner


def _environment():
    return {
        "dataset_fingerprint": "d" * 64,
        "source_sha256": "s" * 64,
        "labels": {"NPA": 321, "PA": 152},
        "applicability": {"not_applicable": 74},
        "tasks": 90,
        "expected_predictions": 4923,
        "model_ids": {"T1": "fake-A", "T2": "fake-B", "T3": "fake-C"},
        "llm_temperature": 0,
        "openrouter_endpoint": "https://example.invalid/api",
        "langfuse_tracing_enabled": True,
        "rag": {"collection": "legal_knowledge", "collection_sha256": "r" * 64},
        "ollama": {"embedding_model": "fake", "endpoint_checked": True},
        "config_sha256": "a" * 64,
        "code_sha256": "o" * 64,
    }


@pytest.fixture
def versioned(tmp_path, monkeypatch):
    baseline = _environment()
    original = {
        "fingerprint": canonical_sha256(baseline),
        "environment": baseline,
    }
    (tmp_path / runner.OLD_PREFLIGHT_FILENAME).write_text(
        json.dumps(original), encoding="utf-8"
    )
    candidate = copy.deepcopy(baseline)
    candidate["config_sha256"] = "b" * 64
    candidate["code_sha256"] = "n" * 64
    monkeypatch.setattr(
        runner, "create_readiness_manifest",
        lambda _root: copy.deepcopy(candidate)
    )
    return tmp_path, candidate


def test_v21_candidate_manifest_freezes_without_provider_calls(versioned):
    root, _candidate = versioned
    baseline_sha = (
        json.loads((root / runner.OLD_PREFLIGHT_FILENAME).read_text())
        ["fingerprint"]
    )
    frozen = runner.freeze_candidate(root)
    assert frozen["candidate"]["candidate_protocol"] == (
        runner.CANDIDATE_PROTOCOL
    )
    assert frozen["candidate"]["baseline_preflight_sha256"] == baseline_sha
    assert len(frozen["fingerprint"]) == 64
    assert runner.verify_candidate(root) == frozen
    assert runner.freeze_candidate(root) == frozen
    assert not (root / runner.OLD_RUN_FILENAME).exists()
    assert not (root / "v2_binary_unit_checkpoints.jsonl").exists()


def test_v21_change_after_freeze_refused(versioned):
    root, candidate = versioned
    runner.freeze_candidate(root)
    candidate["rag"]["collection_sha256"] = "changed"
    with pytest.raises(PreflightError, match="variables controladas"):
        runner.verify_candidate(root)


def test_v21_new_prompt_hash_required(versioned):
    root, candidate = versioned
    candidate["config_sha256"] = "a" * 64
    with pytest.raises(PreflightError, match="idéntico"):
        runner.freeze_candidate(root)


def test_v21_source_mutation_refuses_frozen_candidate(versioned):
    root, candidate = versioned
    runner.freeze_candidate(root)
    candidate["code_sha256"] = "c" * 64
    with pytest.raises(PreflightError, match="cambiaron"):
        runner.verify_candidate(root)


def test_v21_rejects_queued_baseline_job(versioned):
    root, _candidate = versioned
    queue = root / "binary_jobs"
    queue.mkdir()
    (queue / "ET02-R1.json").write_text(
        json.dumps({"status": "queued"}), encoding="utf-8"
    )
    with pytest.raises(PreflightError, match="cola"):
        runner._no_active_v2_jobs(root)


def test_v21_ignores_finished_baseline_job(versioned):
    root, _candidate = versioned
    queue = root / "binary_jobs"
    queue.mkdir()
    (queue / "ET01-R1.json").write_text(
        json.dumps({"status": "completed"}), encoding="utf-8"
    )
    runner._no_active_v2_jobs(root)


def test_v21_requires_complete_baseline_for_comparison(versioned, monkeypatch):
    root, _candidate = versioned
    class Unit:
        technical_id = "ToS01-U001"
    class Data:
        fingerprint = "d" * 64
    with pytest.raises(ValueError, match="No existe ET01-R1 V2"):
        runner._baseline_completed(
            root,
            Data(),
            {"task_id": "ET01-R1"},
            [Unit()],
        )
