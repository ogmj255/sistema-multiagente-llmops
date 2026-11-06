"""Inspección humana sin cambiar predicciones, referencia ni archivos."""

from types import SimpleNamespace

import pytest

from scripts import inspect_v21_disagreements_readonly as inspector


def test_default_ids_cover_four_identified_disagreements():
    assert inspector.DEFAULT_IDS == (
        "ToS02-U001", "ToS02-U002", "ToS02-U011", "ToS02-U023"
    )


def test_inspector_prints_exact_source_and_both_explanations(tmp_path, monkeypatch):
    frozen = {"fingerprint": "preflight"}
    monkeypatch.setattr(inspector, "verify_holdout", lambda _: frozen)
    units = (
        SimpleNamespace(
            technical_id="ToS02-U001", platform="OpenAI",
            original_text="Texto original íntegro, sin cambiar.",
            label="not_applicable", applicability="No aplicable",
        ),
    )
    monkeypatch.setattr(
        inspector, "load_binary_groundtruth_v2",
        lambda _: SimpleNamespace(fingerprint="dataset")
    )
    monkeypatch.setattr(
        inspector, "make_experimental_plan",
        lambda _: {"tasks": [
            {"task_id": inspector.TARGET_TASK_ID, "model": "fake",
             "unit_count": 1}
        ]}
    )
    monkeypatch.setattr(inspector, "document_units", lambda *_: units)
    root = tmp_path / "fake"
    monkeypatch.setattr(inspector, "_root", lambda _: root)
    responses = [
        {"id": "ToS02-U001", "prediction": "no potencialmente abusiva",
         "assessment": {
             "analysis_status": "classified",
             "classification": "not_potentially_abusive",
             "justification": "Razón distinta entre versiones.",
         }},
    ]
    v2 = {"unit_results": responses}
    candidate = {
        "holdout_manifest_fingerprint": "preflight", "unit_results": responses
    }
    monkeypatch.setattr(
        inspector, "_completed_record",
        lambda path, *_: v2 if path == root / inspector.BASELINE_RESULTS
        else candidate,
    )
    result = inspector.inspect(tmp_path, ("ToS02-U001",))
    assert len(result) == 1
    assert result[0]["original_text_complete"] == (
        "Texto original íntegro, sin cambiar."
    )
    assert result[0]["responses"]["v2"]["justification"] == (
        "Razón distinta entre versiones."
    )
    assert result[0]["responses"]["v21"]["analysis_status"] == "classified"
    assert not (tmp_path / "report.json").exists()
    with pytest.raises(ValueError, match="ajenos"):
        inspector.inspect(tmp_path, ("ToS02-U099",))
