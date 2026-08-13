from datetime import UTC, datetime

from app.agents import web_scraper_agent
from app.schemas.contract import (
    ContractSection,
    ExtractedContract,
    ExtractionRequest,
)


def test_agent_uses_playwright_when_static_extraction_fails(
    monkeypatch,
) -> None:
    """Comprueba el cambio del método estático hacia Playwright."""

    request = ExtractionRequest(
        url="https://example.com/terms",
        platform="Example",
    )

    expected_contract = ExtractedContract(
        source_url=request.url,
        platform="Example",
        title="Contrato dinámico de prueba",
        retrieved_at=datetime.now(UTC),
        extraction_method="playwright",
        language="es",
        sections=[
            ContractSection(
                order=1,
                heading="Condiciones",
                content="Contenido dinámico de prueba.",
            )
        ],
        full_text="Contenido dinámico de prueba.",
    )

    def fail_static_extraction(
        _request: ExtractionRequest,
    ) -> None:
        raise ValueError(
            "El HTML estático no contiene el contrato."
        )

    def return_dynamic_contract(
        _request: ExtractionRequest,
    ) -> ExtractedContract:
        return expected_contract

    def accept_contract(
        _contract: ExtractedContract,
    ) -> bool:
        return True

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
        "has_sufficient_contract_content",
        accept_contract,
    )

    response = web_scraper_agent.run_web_scraper_agent(
        request
    )

    assert response.status == "success"
    assert response.contract == expected_contract
    assert response.contract.extraction_method == "playwright"

def test_agent_returns_error_when_both_methods_fail(
    monkeypatch,
) -> None:
    """Comprueba la respuesta cuando ambos métodos fallan."""

    request = ExtractionRequest(
        url="https://example.com/terms",
        platform="Example",
    )

    def fail_extraction(
        _request: ExtractionRequest,
    ) -> None:
        raise ValueError("No se encontró el contrato.")

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

    response = web_scraper_agent.run_web_scraper_agent(request)

    assert response.status == "error"
    assert response.contract is None
    assert response.error is not None
    assert "No se pudo extraer el contrato" in response.error

def test_agent_rejects_insufficient_content(
    monkeypatch,
) -> None:
    """Rechaza contenido insuficiente en ambos métodos."""

    request = ExtractionRequest(
        url="https://example.com/terms",
        platform="Example",
    )

    incomplete_contract = ExtractedContract(
        source_url=request.url,
        platform="Example",
        title="Página incompleta",
        retrieved_at=datetime.now(UTC),
        extraction_method="beautiful_soup",
        language="es",
        sections=[
            ContractSection(
                order=1,
                heading="Aviso",
                content="Contenido parcial.",
            )
        ],
        full_text="Contenido parcial.",
    )

    def return_incomplete_contract(
        _request: ExtractionRequest,
    ) -> ExtractedContract:
        return incomplete_contract

    monkeypatch.setattr(
        web_scraper_agent,
        "extract_static_contract",
        return_incomplete_contract,
    )
    monkeypatch.setattr(
        web_scraper_agent,
        "extract_dynamic_contract",
        return_incomplete_contract,
    )

    response = web_scraper_agent.run_web_scraper_agent(
        request
    )

    assert response.status == "error"
    assert response.contract is None
    assert response.error is not None
    assert "contenido dinámico es insuficiente" in (
        response.error.lower()
    )