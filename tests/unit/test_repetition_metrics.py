"""Métricas experimentales (4 clases, evaluables, 3 repeticiones) sin red."""

import pytest

from app.evaluation.design import DOCUMENTS, make_experimental_plan
from app.evaluation.groundtruth import GroundTruth, GroundTruthUnit
from app.evaluation.binary_groundtruth import BINARY_LABELS as LABELS
from app.evaluation.repetition_metrics import score_campaign_repetitions


def sample_groundtruth() -> GroundTruth:
    items = []
    n = 0
    for document, platform, count in DOCUMENTS:
        for i in range(1, count + 1):
            label = LABELS[n % 3]
            items.append(GroundTruthUnit(
                technical_id=f"{document}-U{i:03d}",
                platform=platform,
                original_text=f"Cláusula congelada {n}",
                applicability=(
                    "No aplicable" if label == "not_applicable"
                    else "Evaluable"
                ),
                label=label,
                text_sha256="a" * 64,
            ))
            n += 1
    return GroundTruth(
        units=tuple(items),
        fingerprint="f" * 64,
        source_sha256="b" * 64,
    )


def completed_task(task, data):
    units = [
        unit for unit in data.units
        if unit.technical_id.startswith(task["document_id"] + "-U")
    ]
    return {
        "task_id": task["task_id"],
        "combination_id": task["combination_id"],
        "treatment": task["treatment"],
        "model": task["model"],
        "repetition": task["repetition"],
        "document_id": task["document_id"],
        "dataset_fingerprint": data.fingerprint,
        "status": "success",
        "unit_results": [
            {
                "id": unit.technical_id,
                "status": "success",
                "prediction": unit.label,
            }
            for unit in units
        ],
        "report": {
            "total_clauses": len(units),
            "successful_clauses": len(units),
        },
        "llm_metrics": [{"cost_usd": 0.002}],
        "duration_ms": 100,
    }


def test_nine_cells_have_fixed_denominators_without_predictions():
    data = sample_groundtruth()
    result = score_campaign_repetitions(data, [])
    assert result["results_are_final"] is False
    assert len(result["by_treatment_repetition"]) == 9
    for row in result["by_treatment_repetition"]:
        assert row["total_units"] == 547
        assert row["predictions_valid"] == 0
        assert row["missing_or_invalid"] == 547
        assert row["documents_pending"] == 10
        assert row["all_units"]["coverage"] == 0
    assert all(
        model["f1_macro_mean"] is None
        for model in result["model_aggregate"]
    )


def test_full_model_one_repetition_yields_perfect_scores_but_not_final():
    data = sample_groundtruth()
    plan = make_experimental_plan(data)
    selected = [
        task for task in plan["tasks"]
        if task["treatment"] == "T1" and task["repetition"] == 1
    ]
    records = [completed_task(task, data) for task in selected]
    result = score_campaign_repetitions(data, records)
    row = next(
        item for item in result["by_treatment_repetition"]
        if item["treatment"] == "T1" and item["repetition"] == 1
    )
    assert row["is_complete"] is True
    assert row["documents_completed"] == 10
    assert row["all_units"]["accuracy"] == 1.0
    assert row["all_units"]["f1_macro"] == 1.0
    assert row["evaluable_units"]["accuracy"] == 1.0
    assert row["cost_usd_reported"] == 0.02
    assert result["results_are_final"] is False


def test_ninety_completed_tasks_allow_three_repetition_summary():
    data = sample_groundtruth()
    tasks = make_experimental_plan(data)["tasks"]
    records = [completed_task(task, data) for task in tasks]
    result = score_campaign_repetitions(data, records)
    assert result["results_are_final"] is True
    assert result["design_predictions"] == 4923
    assert all(
        entry["f1_macro_mean"] == 1.0
        and entry["f1_macro_sample_sd"] == 0.0
        and entry["complete_repetitions"] == 3
        for entry in result["model_aggregate"]
    )


def test_rate_limited_attempt_is_operationally_missing():
    data = sample_groundtruth()
    task = make_experimental_plan(data)["tasks"][0]
    fail = completed_task(task, data)
    fail["status"] = "error"
    fail["unit_results"] = [
        {"id": "ToS01-U001", "status": "error", "prediction": None}
    ]
    fail["report"] = None
    result = score_campaign_repetitions(data, [fail])
    row = result["by_treatment_repetition"][0]
    assert row["documents_incomplete"] == 1
    assert row["predictions_valid"] == 0
    assert row["missing_or_invalid"] == 547
    assert row["is_complete"] is False


def test_rejects_wrong_model_or_fingerprint():
    data = sample_groundtruth()
    task = make_experimental_plan(data)["tasks"][0]
    record = completed_task(task, data)
    with pytest.raises(ValueError, match="incompatible"):
        score_campaign_repetitions(data, [{
            **record, "dataset_fingerprint": "wrong",
        }])
    with pytest.raises(ValueError, match="incompatible"):
        score_campaign_repetitions(data, [{
            **record, "model": "wrong",
        }])


def test_rejects_duplicate_or_foreign_unit_ids():
    data = sample_groundtruth()
    task = make_experimental_plan(data)["tasks"][0]
    first = completed_task(task, data)
    first["unit_results"] = first["unit_results"] + [first["unit_results"][0]]
    first["status"] = "error"
    with pytest.raises(ValueError, match="duplicada"):
        score_campaign_repetitions(data, [first])

    second = completed_task(task, data)
    second["unit_results"] = [
        {"id": "ToS10-U048", "status": "success",
         "prediction": "potencialmente abusiva"},
    ]
    second["status"] = "error"
    with pytest.raises(ValueError, match="ajena"):
        score_campaign_repetitions(data, [second])


def test_one_document_completed_526_missing_means_pending_not_errors():
    data = sample_groundtruth()
    task = make_experimental_plan(data)["tasks"][0]
    result = score_campaign_repetitions(
        data, [completed_task(task, data)]
    )
    row = result["by_treatment_repetition"][0]
    assert row["documents_completed"] == 1
    assert row["documents_pending"] == 9
    assert row["predictions_valid"] == 21
    assert row["missing_or_invalid"] == 526
    assert row["pending_document_units"] == 526
    assert row["unavailable_in_started_documents"] == 0
    assert row["explicit_unit_errors"] == 0
    assert row["unavailable_prediction_rate"] == round(526 / 547, 6)


def test_observed_provider_failure_not_confused_with_pending_documents():
    data = sample_groundtruth()
    task = make_experimental_plan(data)["tasks"][0]
    fail = completed_task(task, data)
    fail["status"] = "error"
    fail["unit_results"] = [
        {"id": "ToS01-U001", "status": "error", "prediction": None}
    ]
    fail["report"] = None
    row = score_campaign_repetitions(
        data, [fail]
    )["by_treatment_repetition"][0]
    assert row["pending_document_units"] == 526
    assert row["unavailable_in_started_documents"] == 21
    assert row["explicit_unit_errors"] == 1
    assert row["missing_or_invalid"] == 547
