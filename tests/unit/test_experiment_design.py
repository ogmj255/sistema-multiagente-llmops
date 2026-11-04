"""El plan respeta las Tablas 8, 21 y 22 de la tesis."""

from app.evaluation.design import (
    DOCUMENTS,
    EXPECTED_UNITS,
    MODELS,
    REPETITIONS,
    ExperimentalDesignError,
    make_experimental_plan,
)
from app.evaluation.groundtruth import GroundTruth, GroundTruthUnit
import pytest


def fake_groundtruth(*, omit_last: bool = False) -> GroundTruth:
    units = tuple(
        GroundTruthUnit(
            technical_id=f"{document}-U{idx:03d}",
            platform=platform,
            original_text=f"Texto {document}-{idx}",
            applicability="Evaluable",
            label="no potencialmente abusiva",
            text_sha256="0" * 64,
        )
        for document, platform, count in DOCUMENTS
        for idx in range(1, count + 1)
    )
    if omit_last:
        units = units[:-1]
    return GroundTruth(
        units=units,
        fingerprint="f" * 64,
        source_sha256="e" * 64,
    )


def test_plan_follows_research_design() -> None:
    plan = make_experimental_plan(fake_groundtruth())
    assert EXPECTED_UNITS == 547
    assert REPETITIONS == 3
    assert len(MODELS) == 3
    assert plan["combinations"] == 30
    assert plan["executions"] == 90
    assert plan["expected_unit_predictions"] == 547 * 3 * 3
    assert plan["status"] == "planned_not_executed"
    tasks = plan["tasks"]
    assert tasks[0]["task_id"] == "ET01-R1"
    assert tasks[0]["document_id"] == "ToS01"
    assert tasks[0]["treatment"] == "T1"
    assert tasks[-1]["task_id"] == "ET30-R3"
    assert tasks[-1]["document_id"] == "ToS10"
    assert tasks[-1]["treatment"] == "T3"
    assert len({task["task_id"] for task in tasks}) == 90
    assert all("label" not in task for task in tasks)


def test_plan_rejects_missing_document_units() -> None:
    with pytest.raises(ExperimentalDesignError, match="Tabla 8"):
        make_experimental_plan(fake_groundtruth(omit_last=True))
