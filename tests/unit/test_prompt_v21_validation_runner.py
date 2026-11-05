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



def test_v21_comparison_is_paired_and_never_mutates_v2(versioned, monkeypatch):
    root, _candidate = versioned
    class Unit:
        def __init__(self, num, label):
            self.technical_id = f"ToS01-U{num:03d}"
            self.label = label

    units = [
        Unit(n, runner.NPA if n <= 16 else runner.PA)
        for n in range(1, 21)
    ] + [Unit(21, "not_applicable")]
    dataset = type("Dataset", (), {"fingerprint": "d" * 64})()
    task = {"task_id": "ET01-R1", "model": "fake-A", "repetition": 1}
    monkeypatch.setattr(
        runner, "_task_and_dataset", lambda _root: (dataset, task, units)
    )
    old_results = []
    new_results = []
    for n, unit in enumerate(units, start=1):
        old_prediction = (
            "not_applicable" if n == 21 else
            runner.NPA if n <= 7 else runner.PA
        )
        new_prediction = (
            "not_applicable" if n == 21 else
            runner.NPA if n <= 11 else runner.PA
        )
        old_results.append({"id": unit.technical_id, "prediction": old_prediction})
        new_results.append({"id": unit.technical_id, "prediction": new_prediction})
    original = {"execution_id": "old", "status": "success",
                "unit_results": old_results}
    candidate = {"execution_id": "candidate", "status": "success",
                 "unit_results": new_results}
    monkeypatch.setattr(runner, "_baseline_completed",
                        lambda *_args: original)
    monkeypatch.setattr(
        runner, "read_jsonl", lambda path: (
            [candidate] if path.name == runner.CANDIDATE_RUN_FILENAME else []
        )
    )
    monkeypatch.setattr(
        runner, "completed_document_run",
        lambda row, _task, _ids, _fp: row.get("status") == "success",
    )

    def score(_dataset, records):
        improved = records[0]["execution_id"] == "candidate"
        return [{
            "task_id": "ET01-R1",
            "accuracy_evaluable_observed": 0.75 if improved else 0.55,
            "f1_macro_evaluable_observed": 0.70 if improved else 0.5396,
            "binary_confusion_matrix_on_observed": {
                runner.NPA: {runner.NPA: 11 if improved else 7,
                             runner.PA: 5 if improved else 9},
                runner.PA: {runner.NPA: 0, runner.PA: 4},
            },
            "binary_per_class_on_observed": {
                runner.NPA: {"f1": 0.8 if improved else 0.6087},
                runner.PA: {
                    "precision": 4 / (9 if improved else 13),
                    "recall": 1.0,
                },
            },
            "cost_usd_reported": 0.016 if improved else 0.0137,
            "duration_ms_reported": 250000 if improved else 303000,
            "cost_reporting_incomplete_attempts": 0,
            "predictions_valid": 21,
        }]
    monkeypatch.setattr(runner, "score_campaign_documents", score)
    runner.candidate_directory(root).mkdir()
    report = runner._compare_one(root)
    assert report["candidate_passes_exploratory_gate"] is True
    assert report["delta"]["false_positives"] == -4
    assert report["delta"]["false_negatives"] == 0
    assert report["applicability"] == {
        "reference_not_applicable": 1,
        "v2_correct": 1,
        "v2_1_correct": 1,
    }
    assert len(report["changed_unit_predictions"]) == 4
    assert (runner.candidate_directory(root) / "comparison.json").exists()
    assert not (root / runner.OLD_RUN_FILENAME).exists()
