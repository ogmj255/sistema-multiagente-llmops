"""Pruebas sin API ni Ollama del ejecutor experimental."""

import json
from pathlib import Path

from app.evaluation import pilot
from app.evaluation.groundtruth import GroundTruthUnit
from app.llm.models import ModelProviderError, ModelResponse
from app.schemas.knowledge import KnowledgeResponse


def unit() -> GroundTruthUnit:
    return GroundTruthUnit(
        technical_id="ToS01-U001",
        platform="Holded",
        original_text="El proveedor podrá modificar las condiciones.",
        applicability="Evaluable",
        label="ETIQUETA-HUMANA-SECRETA",
        text_sha256="a" * 64,
    )


TASK = {
    "document_id": "ToS01",
    "task_id": "ET01-R1",
    "combination_id": "ET01",
    "repetition": 1,
    "treatment": "T1",
    "model": "deepseek/deepseek-v4-flash-0731",
}


def test_prediction_hides_reference_label(monkeypatch, tmp_path):
    """El prompt contiene texto, nunca la clase del investigador."""
    monkeypatch.setattr(
        pilot, "load_or_retrieve_context",
        lambda *_: ([], "b" * 64, True, 0.0),
    )

    def fake_infer(messages, schema, *, trace_context, model):
        content = json.dumps(
            [message.model_dump() for message in messages],
            ensure_ascii=False,
        )
        assert "ETIQUETA-HUMANA-SECRETA" not in content
        assert "El proveedor podrá modificar" in content
        assert model == TASK["model"]
        assert schema and trace_context["trace_id"]
        return ModelResponse(
            provider="openrouter",
            model=model,
            content=json.dumps({
                "category": "condiciones",
                "clause_type": "modificación",
                "target": "usuario",
                "consequence": None,
                "classification": "potentially_abusive",
                "analysis_status": "classified",
                "justification": "Facultad unilateral.",
                "recommendation": None,
                "evidence_sufficiency": "insufficient",
                "legal_basis_indices": [],
            }),
            prompt_tokens=80,
            completion_tokens=20,
            cost_usd=0.001,
        )

    record = pilot.predict_one(
        unit(), TASK, "f" * 64, tmp_path / "rag.jsonl",
        infer=fake_infer,
    )
    assert record["status"] == "success", record["error"]
    assert record["prediction"] == "potencialmente abusiva"
    assert record["prompt_tokens"] == 80
    assert record["cost_usd"] == 0.001
    assert "ETIQUETA-HUMANA-SECRETA" not in json.dumps(
        record, ensure_ascii=False,
    )


def test_context_is_frozen_and_reused(monkeypatch, tmp_path):
    calls = []
    def fake_knowledge(query):
        calls.append(query)
        return KnowledgeResponse(
            status="success", query=query.query, matches=[],
        )
    monkeypatch.setattr(pilot, "run_knowledge_agent", fake_knowledge)
    request = pilot.make_request(unit())
    path = tmp_path / "rag.jsonl"
    first = pilot.load_or_retrieve_context(unit(), request, path)
    second = pilot.load_or_retrieve_context(unit(), request, path)
    assert len(calls) == 1
    assert first[1] == second[1]
    assert first[2] is False
    assert second[2] is True
    assert path.exists()


def test_provider_error_kept_as_error(monkeypatch, tmp_path):
    monkeypatch.setattr(
        pilot, "load_or_retrieve_context",
        lambda *_: ([], "b" * 64, True, 0.0),
    )
    def raise_provider(*_args, **_kwargs):
        raise ModelProviderError("Simulación controlada: API falló")
    record = pilot.predict_one(
        unit(), TASK, "f" * 64, tmp_path / "rag.jsonl",
        infer=raise_provider,
    )
    assert record["status"] == "provider_error"
    assert record["prediction"] is None
    assert "API falló" in record["error"]


def test_resume_preserves_success_without_duplicate(tmp_path):
    path = tmp_path / "results.jsonl"
    row = {
        "task_id": "ET01-R1", "id": "ToS01-U001",
        "dataset_fingerprint": "f" * 64,
        "status": "success",
    }
    pilot.append_jsonl(path, row)
    loaded = pilot.read_jsonl(path)
    assert pilot.already_completed(
        loaded, task_id="ET01-R1", technical_id="ToS01-U001",
        fingerprint="f" * 64,
    )
    assert pilot.already_completed(
        loaded, task_id="ET01-R1", technical_id="ToS01-U001",
        fingerprint="f" * 64, retry_errors=True,
    )
    assert not pilot.already_completed(
        loaded, task_id="ET02-R1", technical_id="ToS01-U001",
        fingerprint="f" * 64,
    )


def test_not_applicable_classified_from_status(monkeypatch, tmp_path):
    monkeypatch.setattr(
        pilot, "load_or_retrieve_context",
        lambda *_: ([], "b" * 64, True, 0.0),
    )
    def fake_infer(*_args, **_kwargs):
        return ModelResponse(
            provider="openrouter",
            model=str(TASK["model"]),
            content=json.dumps({
                "category": "título",
                "clause_type": "encabezado",
                "target": "usuario",
                "consequence": None,
                "classification": None,
                "analysis_status": "not_applicable",
                "justification": "Título aislado.",
                "recommendation": None,
                "evidence_sufficiency": "insufficient",
                "legal_basis_indices": [],
            }),
        )
    record = pilot.predict_one(
        unit(), TASK, "f" * 64, tmp_path / "rag.jsonl",
        infer=fake_infer,
    )
    assert record["status"] == "success", record["error"]
    assert record["prediction"] == "not_applicable"
