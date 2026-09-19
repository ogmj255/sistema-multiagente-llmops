from datetime import UTC, datetime

from app.agents import web_scraper_agent
from app.schemas.contract import (
    ExtractedContract,
    ExtractionRequest,
)


def create_contract(
    request: ExtractionRequest,
    extraction_method: str,
    raw_html: str,
) -> ExtractedContract:
    """Crea una respuesta del scraper para las pruebas."""

    return ExtractedContract(
        source_url=request.url,
        platform=request.platform or "example.com",
        retrieved_at=datetime.now(UTC),
        extraction_method=extraction_method,
        raw_html=raw_html,
    )


def test_agent_returns_static_html_when_content_is_sufficient(
    monkeypatch,
) -> None:
    """Usa httpx cuando el HTML estático contiene suficiente texto."""

    request = ExtractionRequest(
        url="https://example.com/terms",
        platform="Example",
    )

    static_contract = create_contract(
        request,
        "httpx",
        "<html><body>Contenido estático suficiente.</body></html>",
    )

    dynamic_called = False

    def return_static_contract(
        _request: ExtractionRequest,
    ) -> ExtractedContract:
        return static_contract

    def fail_if_dynamic_called(
        _request: ExtractionRequest,
    ) -> ExtractedContract:
        nonlocal dynamic_called
        dynamic_called = True
        raise AssertionError(
            "Playwright no debe ejecutarse cuando el HTML estático es suficiente."
        )

    monkeypatch.setattr(
        web_scraper_agent,
        "extract_static_contract",
        return_static_contract,
    )

    monkeypatch.setattr(
        web_scraper_agent,
        "extract_dynamic_contract",
        fail_if_dynamic_called,
    )

    monkeypatch.setattr(
        web_scraper_agent,
        "has_sufficient_html_content",
        lambda raw_html: True,
    )

    response = web_scraper_agent.run_web_scraper_agent(
        request
    )

    assert response.status == "success"
    assert response.contract == static_contract
    assert response.contract.extraction_method == "httpx"
    assert dynamic_called is False


def test_agent_uses_playwright_when_static_extraction_fails(
    monkeypatch,
) -> None:
    """Usa Playwright cuando la extracción estática falla."""

    request = ExtractionRequest(
        url="https://example.com/terms",
        platform="Example",
    )

    dynamic_contract = create_contract(
        request,
        "playwright",
        "<html><body>Contenido dinámico.</body></html>",
    )

    def fail_static_extraction(
        _request: ExtractionRequest,
    ) -> ExtractedContract:
        raise ValueError(
            "No se pudo obtener el HTML estático."
        )

    def return_dynamic_contract(
        _request: ExtractionRequest,
    ) -> ExtractedContract:
        return dynamic_contract

    monkeypatch.setattr(
        web_scraper_agent,
        "extract_static_contract",
        fail_static_extraction,
    )

    monkeypatch.setattr(
        web_scraper_agent,
        "extract_dynamic_contract",
        return_dynamic_contract,
    )

    monkeypatch.setattr(
        web_scraper_agent,
        "has_sufficient_html_content",
        lambda raw_html: True,
    )

    response = web_scraper_agent.run_web_scraper_agent(
        request
    )

    assert response.status == "success"
    assert response.contract == dynamic_contract
    assert response.contract.extraction_method == "playwright"


def test_agent_uses_playwright_when_static_html_is_insufficient(
    monkeypatch,
) -> None:
    """Usa Playwright cuando el HTML estático es insuficiente."""

    request = ExtractionRequest(
        url="https://example.com/terms",
        platform="Example",
    )

    static_contract = create_contract(
        request,
        "httpx",
        "<html><body>Cargando...</body></html>",
    )

    dynamic_contract = create_contract(
        request,
        "playwright",
        "<html><body>Contrato renderizado completo.</body></html>",
    )

    monkeypatch.setattr(
        web_scraper_agent,
        "extract_static_contract",
        lambda _request: static_contract,
    )

    monkeypatch.setattr(
        web_scraper_agent,
        "extract_dynamic_contract",
        lambda _request: dynamic_contract,
    )

    monkeypatch.setattr(
        web_scraper_agent,
        "has_sufficient_html_content",
        lambda raw_html: (
            raw_html == dynamic_contract.raw_html
        ),
    )

    response = web_scraper_agent.run_web_scraper_agent(
        request
    )

    assert response.status == "success"
    assert response.contract == dynamic_contract
    assert response.contract.extraction_method == "playwright"


def test_agent_returns_error_when_both_methods_fail(
    monkeypatch,
) -> None:
    """Devuelve error cuando httpx y Playwright fallan."""

    request = ExtractionRequest(
        url="https://example.com/terms",
        platform="Example",
    )

    def fail_extraction(
        _request: ExtractionRequest,
    ) -> ExtractedContract:
        raise ValueError(
            "No se pudo obtener el documento HTML."
        )

    monkeypatch.setattr(
        web_scraper_agent,
        "extract_static_contract",
        fail_extraction,
    )

    monkeypatch.setattr(
        web_scraper_agent,
        "extract_dynamic_contract",
        fail_extraction,
    )

    response = web_scraper_agent.run_web_scraper_agent(
        request
    )

    assert response.status == "error"
    assert response.contract is None
    assert response.error is not None
    assert "No se pudo extraer el HTML" in response.error


def test_agent_returns_error_when_dynamic_html_is_also_insufficient(
    monkeypatch,
) -> None:
    """Devuelve error si ningun metodo obtiene contenido suficiente."""

    request = ExtractionRequest(
        url="https://example.com/terms",
        platform="Example",
    )

    static_contract = create_contract(
        request,
        "httpx",
        "<html><body>Cargando...</body></html>",
    )

    dynamic_contract = create_contract(
        request,
        "playwright",
        "<html><body>Sin contenido contractual.</body></html>",
    )

    monkeypatch.setattr(
        web_scraper_agent,
        "extract_static_contract",
        lambda _request: static_contract,
    )

    monkeypatch.setattr(
        web_scraper_agent,
        "extract_dynamic_contract",
        lambda _request: dynamic_contract,
    )

    monkeypatch.setattr(
        web_scraper_agent,
        "has_sufficient_html_content",
        lambda raw_html: False,
    )

    response = web_scraper_agent.run_web_scraper_agent(
        request
    )

    assert response.status == "error"
    assert response.contract is None
    assert response.error is not None
    assert "suficiente texto visible" in response.error
