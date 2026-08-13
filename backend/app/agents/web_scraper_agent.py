import httpx
from playwright.sync_api import Error as PlaywrightError

from app.schemas.contract import ExtractionRequest, ExtractionResponse
from app.services.web_scraper import (
    extract_dynamic_contract,
    extract_static_contract,
    has_sufficient_contract_content,
)


def run_web_scraper_agent(
    request: ExtractionRequest,
) -> ExtractionResponse:
    """Coordina la extracción de un contrato desde una URL pública."""

    try:
        contract = extract_static_contract(request)

        if not has_sufficient_contract_content(contract):
            raise ValueError(
                "El contenido estático es insuficiente."
            )

    except (httpx.HTTPError, ValueError):
        try:
            contract = extract_dynamic_contract(request)

            if not has_sufficient_contract_content(contract):
                raise ValueError(
                    "El contenido dinámico es insuficiente."
                )

        except (PlaywrightError, ValueError) as error:
            return ExtractionResponse(
                status="error",
                error=f"No se pudo extraer el contrato: {error}",
            )

    return ExtractionResponse(
        status="success",
        contract=contract,
    )
