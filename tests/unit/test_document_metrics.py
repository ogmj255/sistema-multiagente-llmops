"""La calidad del ToS analizado no se diluye con 526 unidades pendientes."""

from dataclasses import replace

from app.evaluation.design import DOCUMENTS, make_experimental_plan
from app.evaluation.document_metrics import score_campaign_documents
from app.evaluation.groundtruth import GroundTruth, GroundTruthUnit, LABELS


def frozen_dataset():
    units = []
    for document, platform, count in DOCUMENTS:
        for n in range(1, count + 1):
            if document == "ToS01":
                if n == 1:
                    label = "not_applicable"
                elif n <= 17:
                    label = "no potencialmente abusiva"
                else:
                    label = "potencialmente abusiva"
            else:
                label = "no potencialmente abusiva"
            units.append(GroundTruthUnit(
                technical_id=f"{document}-U{n:03d}",
                platform=platform,
                original_text=f"Texto congelado del fragmento {document} {n}.",
                applicability=(
                    "No aplicable" if label == "not_applicable"
                    else "Evaluable"
                ),
                label=label,
                text_sha256="a" * 64,
            ))
    return GroundTruth(
        units=tuple(units),
        fingerprint="f" * 64,
        source_sha256="b" * 64,
    )


def holded_result(dataset):
    task = make_experimental_plan(dataset)["tasks"][0]
    items = [
        unit for unit in dataset.units
        if unit.technical_id.startswith("ToS01-U")
    ]
    predictions = []
    for n, unit in enumerate(items, 1):
        if n == 1:
            label = "not_applicable"
        elif n <= 7:
            label = "no potencialmente abusiva"
        elif n <= 14:
            label = "potencialmente abusiva"
        else:
            label = "potencialmente abusiva"
        predictions.append({
            "id": unit.technical_id,
            "status": "success",
            "prediction": label,
        })
    return {
        "task_id": task["task_id"],
        "model": task["model"],
        "repetition": task["repetition"],
        "dataset_fingerprint": dataset.fingerprint,
        "status": "success",
        "unit_results": predictions,
        "report": {"total_clauses": 21, "successful_clauses": 21},
        "llm_metrics": [{"cost_usd": 0.0215251}],
        "duration_ms": 1301697.229,
    }


def test_holded_21_predictions_produce_document_accuracy_not_547_accuracy():
    dataset = frozen_dataset()
    results = score_campaign_documents(dataset, [holded_result(dataset)])
    assert len(results) == 90
    completed = results[0]
    assert completed["task_id"] == "ET01-R1"
    assert completed["status"] == "completed"
    assert completed["unit_count"] == 21
    assert completed["predictions_valid"] == 21
    assert completed["correct_on_observed"] == 11
    assert completed["accuracy_on_observed"] == 0.52381
    assert completed["f1_macro_on_observed"] > 0.66
    assert completed["accuracy_evaluable_observed"] == 0.5
    assert completed["f1_macro_evaluable_observed"] == 0.49495
    assert completed["quality_is_final_for_document"] is True
    assert completed["explicit_unit_errors"] == 0
    assert completed["confusion_matrix_on_observed"][
        "potencialmente abusiva"
    ]["potencialmente abusiva"] == 4
    assert completed["confusion_matrix_on_observed"][
        "no potencialmente abusiva"
    ]["potencialmente abusiva"] == 7
    assert completed["cost_usd_reported"] == 0.0215251

    not_run = results[1]
    assert not_run["status"] == "not_executed"
    assert not_run["unit_count"] == 21
    assert not_run["accuracy_on_observed"] is None
    assert not_run["f1_macro_on_observed"] is None
    assert not_run["explicit_unit_errors"] == 0


def test_failed_document_quality_is_provisional_not_final():
    dataset = frozen_dataset()
    failure = holded_result(dataset)
    failure["status"] = "partial"
    failure["report"] = None
    failure["unit_results"] = [
        failure["unit_results"][0],
        {"id": "ToS01-U002", "status": "error", "prediction": None},
    ]
    detail = score_campaign_documents(dataset, [failure])
    row = detail[0]
    assert row["status"] == "incomplete"
    assert row["unit_count"] == 21
    assert row["predictions_valid"] == 1
    assert row["predictions_missing"] == 20
    assert row["explicit_unit_errors"] == 1
    assert row["accuracy_on_observed"] == 1.0
    assert row["quality_is_final_for_document"] is False


def test_not_attempted_is_not_mislabeled_as_operational_failure():
    data = frozen_dataset()
    all_docs = score_campaign_documents(data, [])
    assert len(all_docs) == 90
    assert all(row["status"] == "not_executed" for row in all_docs)
    assert all(row["explicit_unit_errors"] == 0 for row in all_docs)
    assert all(row["accuracy_on_observed"] is None for row in all_docs)
