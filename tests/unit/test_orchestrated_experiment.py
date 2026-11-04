"""Prueba de integración simulada de LangGraph + rutas MCP sin gastar API."""

import asyncio
import json
from contextlib import nullcontext

import pytest

from app.agents.observability_agent import build_observability_summary
from app.agents.report_generator_agent import run_report_generator_agent
from app.evaluation import orchestrated
from app.evaluation.groundtruth import GroundTruthUnit
from app.mcp.registry import ClienteMCP, SERVIDORES_MCP
from app.schemas.legal_analysis import ClauseAnalysisResponse, ClauseAssessment
from app.schemas.report import ReportGenerationRequest


class FakeMCP:
    """Emula el transporte; se verifican los agentes y grafo existentes."""

    calls: list[tuple[str, dict[str, object]]] = []
    instances: list[dict[str, object]] = []

    def __init__(self, **kwargs):
        self.instances.append(kwargs)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return None

    async def invocar(self, key, arguments):
        self.calls.append((key, arguments))
        if key == "conocimiento_juridico":
            return {
                "status": "success",
                "query": arguments["query"],
                "matches": [],
            }
        if key == "analizador_legal":
            assessment = ClauseAssessment(
                category="Condiciones generales",
                clause_type="Facultad contractual",
                target="usuario",
                classification="potentially_abusive",
                analysis_status="classified",
                relevant_fragment=arguments["clause"]["content"],
                justification="Posible desequilibrio.",
                evidence_sufficiency="insufficient",
                legal_basis=[],
            )
            return ClauseAnalysisResponse(
                status="success",
                result=assessment,
            ).model_dump(mode="json")
        if key == "generador_informes":
            request = ReportGenerationRequest.model_validate(arguments["request"])
            return run_report_generator_agent(request).model_dump(mode="json")
        if key == "observabilidad":
            return build_observability_summary(
                status=arguments["status"],
                duration_ms=arguments["duration_ms"],
                llm_metrics=[],
                error_count=arguments["error_count"],
            ).model_dump(mode="json")
        raise AssertionError(f"Servidor MCP no esperado: {key}")


def sample_unit():
    return GroundTruthUnit(
        technical_id="ToS01-U001",
        platform="Holded",
        original_text="Texto contractual, sin etiqueta humana.",
        applicability="Evaluable",
        label="ETIQUETA_HUMANA_QUE_NO_DEBE_VIAJAR",
        text_sha256="a" * 64,
    )


def task(model="deepseek/deepseek-v4-flash-0731"):
    return {
        "task_id": "ET01-R1",
        "combination_id": "ET01",
        "treatment": "T1",
        "model": model,
        "repetition": 1,
        "document_id": "ToS01",
        "platform": "Holded",
    }


def test_mcp_model_override_is_isolated():
    analyst = SERVIDORES_MCP["analizador_legal"]
    params = analyst.crear_parametros(
        {"OPENROUTER_MODEL": "mistralai/mistral-large-2512"}
    )
    assert params.env["OPENROUTER_MODEL"] == "mistralai/mistral-large-2512"
    with pytest.raises(ValueError, match="no autorizadas"):
        analyst.crear_parametros({"OPENROUTER_API_KEY_FAKE": "x"})
    with pytest.raises(ValueError, match="desconocido"):
        ClienteMCP(required_servers=("undefined-mcp",))


def test_frozen_contract_never_includes_human_labels():
    doc = orchestrated.fixed_contract([sample_unit()], "ToS01", "Holded")
    data = json.dumps(doc.model_dump(mode="json"), ensure_ascii=False)
    assert "Texto contractual, sin etiqueta humana." in data
    assert "ETIQUETA_HUMANA_QUE_NO_DEBE_VIAJAR" not in data
    assert len(doc.clauses) == 1


def test_actual_langgraph_nodes_route_through_mcp(monkeypatch, tmp_path):
    FakeMCP.calls = []
    FakeMCP.instances = []
    monkeypatch.setattr(orchestrated, "ClienteMCP", FakeMCP)
    monkeypatch.setattr(
        orchestrated, "start_pipeline_observation",
        lambda _execution_id: nullcontext(None),
    )
    monkeypatch.setattr(
        orchestrated, "update_pipeline_observation",
        lambda *_args, **_kwargs: None,
    )

    cache = tmp_path / "contexts.jsonl"
    first = asyncio.run(
        orchestrated.run_orchestrated_trial(
            [sample_unit()],
            task=task(),
            dataset_fingerprint="f" * 64,
            context_cache=cache,
        )
    )
    assert first["status"] == "success", first["errors"]
    assert first["unit_results"][0]["prediction"] == "potencialmente abusiva"
    assert first["report"]["total_clauses"] == 1
    assert first["rag_retrievals"] == 1
    assert first["rag_reuses"] == 0
    assert set(key for key, _ in FakeMCP.calls) == {
        "conocimiento_juridico", "analizador_legal",
        "generador_informes", "observabilidad",
    }
    assert FakeMCP.instances[0]["environment_overrides"] == {
        "analizador_legal": {"OPENROUTER_MODEL": task()["model"]}
    }
    assert "ETIQUETA_HUMANA_QUE_NO_DEBE_VIAJAR" not in json.dumps(
        first, ensure_ascii=False
    )
    assert first["workflow"]["scraping"].startswith("skipped")

    FakeMCP.calls.clear()
    other_model = "mistralai/mistral-large-2512"
    second = asyncio.run(
        orchestrated.run_orchestrated_trial(
            [sample_unit()],
            task=task(other_model),
            dataset_fingerprint="f" * 64,
            context_cache=cache,
        )
    )
    assert second["status"] == "success", second["errors"]
    assert second["rag_reuses"] == 1
    assert second["rag_retrievals"] == 0
    assert "conocimiento_juridico" not in [
        key for key, _ in FakeMCP.calls
    ]
    assert "analizador_legal" in [key for key, _ in FakeMCP.calls]
    assert FakeMCP.instances[1]["environment_overrides"] == {
        "analizador_legal": {"OPENROUTER_MODEL": other_model}
    }
