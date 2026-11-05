"""Control metodológico de validación apareada V2 vs V2.1 sin llamadas pagadas."""

import json
from types import SimpleNamespace

import pytest

from app.evaluation.pilot import canonical_sha256
from app.evaluation.readiness import PreflightError
from scripts import validate_v21_holdout as holdout


@pytest.fixture
def frozen(tmp_path, monkeypatch):
    root = tmp_path
    marker = {
        "profile": "V2.1_holdout_pre_registered",
        "target_task": {"task_id": "ET04-R1", "unit_count": 40},
        "comparison_gate": holdout.PREDEFINED_GATE,
    }
    monkeypatch.setattr(
        holdout, "_holdout_frozen_payload", lambda _: dict(marker)
    )
    return root, marker


def test_holdout_preregistration_is_idempotent_and_keeps_v2(frozen):
    root, _ = frozen
    old = root / "v2_binary_preflight_manifest.json"
    old.write_text('{"sentinel": true}', encoding="utf-8")
    initial = holdout.freeze_holdout(root)
    assert holdout.verify_holdout(root) == initial
    assert holdout.freeze_holdout(root) == initial
    assert json.loads(old.read_text()) == {"sentinel": True}
    assert not (root / "v2_binary_campaign_runs.jsonl").exists()
    assert initial["pre_registered"]["target_task"]["unit_count"] == 40


def test_holdout_refuses_config_drift(frozen, monkeypatch):
    root, marker = frozen
    holdout.freeze_holdout(root)
    marker["target_task"]["unit_count"] = 41
    monkeypatch.setattr(
        holdout, "_holdout_frozen_payload", lambda _: dict(marker)
    )
    with pytest.raises(PreflightError, match="cambiaron"):
        holdout.verify_holdout(root)


def test_holdout_requires_exactly_one_full_attempt(tmp_path, monkeypatch):
    filename = tmp_path / "baseline.jsonl"
    monkeypatch.setattr(holdout, "read_jsonl", lambda path: [])
    with pytest.raises(ValueError, match="exactamente una"):
        holdout._completed_record(filename, {}, [], "fingerprint")

    rows = [{"status": "success"}, {"status": "error"}]
    monkeypatch.setattr(holdout, "read_jsonl", lambda path: rows)
    monkeypatch.setattr(
        holdout, "completed_document_run",
        lambda r, _t, _ids, _fp: r["status"] == "success",
    )
    with pytest.raises(ValueError, match="2 intentos"):
        holdout._completed_record(filename, {}, [], "fingerprint")


def test_holdout_exact_mcnemar_pairs():
    assert holdout._exact_mcnemar(0, 0) == 1.0
    assert holdout._exact_mcnemar(0, 5) == 0.0625
    assert holdout._exact_mcnemar(1, 3) == 0.625


def test_holdout_rag_snapshots_are_checked_by_sha(tmp_path, monkeypatch):
    result = {"status": "success", "matches": []}
    row = {
        "configuration": {"fingerprint": "a", "query_sha256": "x"},
        "response_sha256": canonical_sha256(result),
        "response": result,
    }
    monkeypatch.setattr(holdout, "read_jsonl", lambda path: [row])
    mapped = holdout._rag_snapshot_map(tmp_path / "cache.jsonl")
    assert len(mapped) == 1
    row["response_sha256"] = "incorrect"
    with pytest.raises(ValueError, match="no verificable"):
        holdout._rag_snapshot_map(tmp_path / "cache.jsonl")


def test_holdout_gate_requires_identical_rag_and_nonworsening_fn_na(
    frozen, monkeypatch
):
    root, _marker = frozen
    holdout.freeze_holdout(root)
    folder = holdout._root(root)
    units = [
        SimpleNamespace(technical_id="ToS02-U001", label=holdout.NPA),
        SimpleNamespace(technical_id="ToS02-U002", label=holdout.NPA),
        SimpleNamespace(technical_id="ToS02-U003", label=holdout.NPA),
        SimpleNamespace(technical_id="ToS02-U004", label=holdout.PA),
        SimpleNamespace(technical_id="ToS02-U005", label="not_applicable"),
    ]
    ds = SimpleNamespace(fingerprint="dataset")
    task = {"task_id": holdout.TARGET_TASK_ID}
    monkeypatch.setattr(
        holdout, "_units",
        lambda _: (ds, task, units, [u.technical_id for u in units]),
    )
    old_predictions = [holdout.PA, holdout.NPA, holdout.PA, holdout.PA,
                       "not_applicable"]
    new_predictions = [holdout.NPA, holdout.NPA, holdout.PA, holdout.PA,
                       "not_applicable"]

    def rec(execution_id, labels):
        return {
            "execution_id": execution_id,
            "unit_results": [
                {"id": u.technical_id, "prediction": label}
                for u, label in zip(units, labels, strict=True)
            ],
        }

    old_row = rec("old", old_predictions)
    new_row = rec("new", new_predictions)
    new_row["holdout_manifest_fingerprint"] = (
        holdout.verify_holdout(root)["fingerprint"]
    )
    monkeypatch.setattr(
        holdout, "_completed_record",
        lambda path, *_: (
            old_row if path == folder / holdout.BASELINE_RESULTS else new_row
        )
    )

    def fake_scores(_dataset, records):
        is_new = records[0] is new_row
        return [{
            "task_id": holdout.TARGET_TASK_ID,
            "accuracy_evaluable_observed": 0.75 if is_new else 0.5,
            "f1_macro_evaluable_observed": 0.75 if is_new else 0.50,
            "binary_confusion_matrix_on_observed": {
                holdout.NPA: {holdout.NPA: 2 if is_new else 1,
                              holdout.PA: 1 if is_new else 2},
                holdout.PA: {holdout.NPA: 0, holdout.PA: 1},
            },
            "binary_per_class_on_observed": {
                holdout.NPA: {"f1": 0.8 if is_new else 0.5},
                holdout.PA: {"f1": 0.65 if is_new else 0.5,
                             "recall": 1.0},
            },
            "duration_ms_reported": 1000.0,
            "cost_usd_reported": 0.01,
            "cost_reporting_incomplete_attempts": 0,
        }]

    monkeypatch.setattr(holdout, "score_campaign_documents", fake_scores)
    state = {"same": True}
    monkeypatch.setattr(
        holdout, "_rag_snapshot_map",
        lambda path: (
            {f"{i}": "x" for i in range(len(units))}
            if "v2_baseline" in str(path) or state["same"]
            else {f"{i}": "different" for i in range(len(units))}
        ),
    )
    result = holdout.compare_holdout(root)
    assert result["passes_preregistered_gate"] is True
    assert result["deltas"]["false_positives"] == -1
    assert result["rag_context_control"]["exact_response_sha_equivalent"] is True
    assert result["paired_accuracy_test"]["v21_only_correct"] == 1
    (folder / "comparison.json").unlink()
    state["same"] = False
    result = holdout.compare_holdout(root)
    assert result["rag_context_control"]["exact_response_sha_equivalent"] is False
    assert result["passes_preregistered_gate"] is False
