"""429, Retry-After, límites y coordinación LangGraph — sin red ni costos."""

import asyncio
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx
import pytest
from pydantic import SecretStr

from app.agents import orchestrator_agent
from app.agents import legal_analyzer_agent
from app.llm import openrouter_client
from app.llm.models import ChatMessage
from app.schemas.knowledge import KnowledgeResponse
from app.schemas.legal_analysis import ClauseAnalysisRequest
from app.schemas.preprocessing import ProcessedClause
from app.services.analysis import ClauseClassificationError


def prepare(monkeypatch):
    monkeypatch.setattr(
        openrouter_client.settings, "openrouter_api_key", SecretStr("mock-token")
    )
    monkeypatch.setattr(
        openrouter_client.settings, "openrouter_retry_max_attempts", 3
    )
    monkeypatch.setattr(
        openrouter_client.settings, "openrouter_retry_initial_delay_seconds", 2.0
    )
    monkeypatch.setattr(
        openrouter_client.settings, "openrouter_retry_max_delay_seconds", 30.0
    )
    monkeypatch.setattr(
        openrouter_client, "start_llm_generation",
        lambda *_args, **_kwargs: nullcontext(None)
    )
    observed = []
    monkeypatch.setattr(
        openrouter_client, "mark_llm_generation_error",
        lambda _o, error: observed.append(("error", str(error)))
    )
    monkeypatch.setattr(
        openrouter_client, "update_llm_generation",
        lambda _o, **kwargs: observed.append(("success", kwargs["model"]))
    )
    sleeps = []
    monkeypatch.setattr(openrouter_client.time, "sleep", sleeps.append)
    return sleeps, observed


def request():
    return [ChatMessage(role="user", content="Analiza una cláusula de prueba.")]


def response(status, *, retry_after=None):
    headers = {"Retry-After": retry_after} if retry_after is not None else {}
    if status == 200:
        return httpx.Response(
            200,
            json={
                "model": "mistralai/mistral-large-2512",
                "choices": [{"message": {"content": '{"status": "ok"}'}}],
                "usage": {
                    "prompt_tokens": 11,
                    "completion_tokens": 7,
                    "cost": 0.003,
                },
            },
            request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"),
        )
    return httpx.Response(
        status,
        json={"error": {"message": "simulated HTTP error"}},
        headers=headers,
        request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"),
    )


def test_429_retry_after_then_success(monkeypatch):
    sleeps, events = prepare(monkeypatch)
    received = []
    values = iter([response(429, retry_after="7"), response(200)])

    def fake_post(*_args, **kwargs):
        received.append(kwargs["json"]["model"])
        return next(values)

    monkeypatch.setattr(openrouter_client.httpx, "post", fake_post)
    result = openrouter_client.generate_with_openrouter(
        request(), model="mistralai/mistral-large-2512"
    )
    assert received == ["mistralai/mistral-large-2512"] * 2
    assert sleeps == [7.0]
    assert result.request_attempts == 2
    assert result.http_429_count == 1
    assert result.cost_usd == 0.003
    assert [event[0] for event in events] == ["error", "success"]


def test_429_exhausts_three_attempts_without_orchestrator_multiplication(monkeypatch):
    sleeps, events = prepare(monkeypatch)
    count = []
    def fake_post(*_args, **kwargs):
        count.append(1)
        return response(429)
    monkeypatch.setattr(openrouter_client.httpx, "post", fake_post)

    with pytest.raises(
        openrouter_client.OpenRouterClientError, match="3 intento"
    ) as raised:
        openrouter_client.generate_with_openrouter(request())
    assert raised.value.status_code == 429
    assert raised.value.attempts == 3
    assert len(count) == 3
    assert sleeps == [2.0, 4.0]
    assert len([k for k, _ in events if k == "error"]) == 3


def test_retry_after_larger_than_cap_aborts_without_early_retry(monkeypatch):
    sleeps, _events = prepare(monkeypatch)
    count = []
    def fake_post(*_args, **_kwargs):
        count.append(1)
        return response(429, retry_after="120")
    monkeypatch.setattr(openrouter_client.httpx, "post", fake_post)
    with pytest.raises(
        openrouter_client.OpenRouterClientError, match="Retry-After"
    ) as raised:
        openrouter_client.generate_with_openrouter(request())
    assert raised.value.attempts == 1
    assert count == [1]
    assert sleeps == []


def test_http_date_retry_after(monkeypatch):
    prepare(monkeypatch)
    future = format_datetime(datetime.now(UTC) + timedelta(seconds=12), usegmt=True)
    parsed = openrouter_client._retry_after_seconds(future)
    assert parsed is not None
    assert 9 <= parsed <= 12


def test_non_retryable_http_errors_are_not_repeated(monkeypatch):
    sleeps, _events = prepare(monkeypatch)
    count = []
    def fake_post(*_args, **_kwargs):
        count.append(1)
        return response(401)
    monkeypatch.setattr(openrouter_client.httpx, "post", fake_post)
    with pytest.raises(
        openrouter_client.OpenRouterClientError, match="HTTP 401"
    ) as raised:
        openrouter_client.generate_with_openrouter(request())
    assert raised.value.status_code == 401
    assert count == [1]
    assert sleeps == []


def analysis_request():
    return ClauseAnalysisRequest(
        source_url="https://example.com/terms",
        platform="Example",
        language="es",
        clause=ProcessedClause(
            order=1, original_order=1, content="El proveedor puede cambiar términos."
        ),
    )


def test_mcp_marks_exhausted_rate_limit_as_typed_error(monkeypatch):
    def fail(*_args, **_kwargs):
        try:
            raise openrouter_client.OpenRouterClientError(
                "OpenRouter HTTP 429 tras 3 intento(s).",
                status_code=429,
                attempts=3,
            )
        except openrouter_client.OpenRouterClientError as root:
            raise ClauseClassificationError("Proveedor: 429.") from root

    monkeypatch.setattr(legal_analyzer_agent, "classify_clause", fail)
    result = legal_analyzer_agent.run_legal_analyzer_execution_with_context(
        analysis_request(), []
    )
    assert result.response.status == "error"
    assert result.response.error_code == "provider_rate_limited"


def test_orchestrator_does_not_repeat_typed_provider_http_errors():
    calls = []
    class FakeMCP:
        async def invocar(self, key, args):
            calls.append(key)
            return {
                "analysis": {
                    "status": "error",
                    "error": "OpenRouter HTTP 429 tras 3 intentos.",
                    "error_code": "provider_rate_limited",
                },
                "observability": None,
            }

    async def invoke():
        return await orchestrator_agent.ejecutar_con_reintentos(
            lambda: orchestrator_agent.analizar_clausula(
                analysis_request(),
                KnowledgeResponse(status="success", query="prueba", matches=[]),
                FakeMCP(),
            )
        )

    with pytest.raises(
        orchestrator_agent.ErrorProveedorNoReintentable,
        match="429",
    ):
        asyncio.run(invoke())
    assert calls == ["analizador_legal"]
    state = orchestrator_agent.crear_actualizacion_error_clausula(
        "legal_analysis", 1,
        orchestrator_agent.ErrorProveedorNoReintentable("429"),
    )
    assert state["attempts"]["legal_analysis:1"] == 1
    assert state["errors"][0]["retryable"] is False
