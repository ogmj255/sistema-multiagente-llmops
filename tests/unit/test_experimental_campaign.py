"""Campaña documental: integridad, estados y reanudación sin red ni API."""

from app.evaluation.campaign import (
    completed_document_run,
    document_units,
    run_classification,
    sum_reported_cost,
    task_progress,
)
from app.evaluation.design import DOCUMENTS, make_experimental_plan
from app.evaluation.groundtruth import GroundTruth, GroundTruthUnit


def dataset():
    units = tuple(
        GroundTruthUnit(
            technical_id=f"{document}-U{i:03d}",
            platform=platform,
            original_text=f"Texto original {document} {i}",
            applicability="Evaluable",
            label="no potencialmente abusiva",
            text_sha256="a" * 64,
        )
        for document, platform, count in DOCUMENTS
        for i in range(1, count + 1)
    )
    return GroundTruth(
        units=units, fingerprint="b" * 64, source_sha256="c" * 64
    )


def make_completed(task, units, fingerprint):
    return {
        "task_id": task["task_id"],
        "model": task["model"],
        "repetition": task["repetition"],
        "dataset_fingerprint": fingerprint,
        "status": "success",
        "unit_results": [
            {
                "id": unit.technical_id,
                "status": "success",
                "prediction": "no potencialmente abusiva",
            }
            for unit in units
        ],
        "report": {
            "total_clauses": len(units),
            "successful_clauses": len(units),
        },
        "llm_metrics": [
            {"cost_usd": 0.001},
            {"cost_usd": 0.002},
        ],
    }


def test_document_has_exact_fixed_units_in_original_order():
    data = dataset()
    tasks = make_experimental_plan(data)["tasks"]
    assert len(tasks) == 90
    assert sum(t["unit_count"] for t in tasks) == 4923
    for task in tasks:
        units = document_units(data, task)
        assert len(units) == task["unit_count"]
        assert all(
            unit.technical_id.startswith(task["document_id"] + "-U")
            for unit in units
        )


def test_only_whole_document_counts_as_success():
    data = dataset()
    task = make_experimental_plan(data)["tasks"][0]
    units = document_units(data, task)
    ids = [unit.technical_id for unit in units]
    complete = make_completed(task, units, data.fingerprint)
    assert completed_document_run(complete, task, ids, data.fingerprint)
    assert run_classification(
        [complete], task, ids, data.fingerprint
    ) == "completed"

    shortened = {**complete, "unit_results": complete["unit_results"][:-1]}
    assert not completed_document_run(
        shortened, task, ids, data.fingerprint
    )
    assert run_classification(
        [shortened], task, ids, data.fingerprint
    ) == "failed"

    duplicates = {
        **complete,
        "unit_results": complete["unit_results"][:-1]
        + [complete["unit_results"][0]],
    }
    assert not completed_document_run(
        duplicates, task, ids, data.fingerprint
    )


def test_retry_preserves_prior_failure_and_later_success():
    data = dataset()
    task = make_experimental_plan(data)["tasks"][0]
    units = document_units(data, task)
    ids = [unit.technical_id for unit in units]
    error = {
        "task_id": task["task_id"],
        "model": task["model"],
        "repetition": task["repetition"],
        "dataset_fingerprint": data.fingerprint,
        "status": "error",
        "unit_results": [],
        "llm_metrics": [],
    }
    assert run_classification([error], task, ids, data.fingerprint) == "failed"
    assert run_classification(
        [error, make_completed(task, units, data.fingerprint)],
        task, ids, data.fingerprint,
    ) == "completed"


def test_model_repetition_or_fingerprint_mismatch_is_not_complete():
    data = dataset()
    task = make_experimental_plan(data)["tasks"][0]
    units = document_units(data, task)
    ids = [unit.technical_id for unit in units]
    original = make_completed(task, units, data.fingerprint)
    for key, invalid in (
        ("model", "otro-modelo"),
        ("repetition", 3),
        ("dataset_fingerprint", "0" * 64),
    ):
        item = {**original, key: invalid}
        assert not completed_document_run(item, task, ids, data.fingerprint)


def test_progress_and_cost_aggregation_with_missing_usage():
    data = dataset()
    tasks = make_experimental_plan(data)["tasks"]
    first = tasks[0]
    records = [make_completed(
        first, document_units(data, first), data.fingerprint,
    )]
    progress = task_progress(data, tasks, records)
    assert progress["counts"] == {
        "completed": 1, "failed": 0, "pending": 89,
    }
    assert progress["reported_cost_usd"] == 0.003
    assert sum_reported_cost({
        "llm_metrics": [
            {"cost_usd": None}, {"cost_usd": 0.5}, {},
        ]
    }) == 0.5
