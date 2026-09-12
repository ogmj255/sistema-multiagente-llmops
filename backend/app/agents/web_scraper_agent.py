import httpx
from playwright.sync_api import Error as PlaywrightError

from app.schemas.contract import ExtractionRequest, ExtractionResponse
from app.services.web_scraper import (
    extract_dynamic_contract,
    extract_static_contract,
    get_usable_content_length,
    has_sufficient_contract_content,
)


def run_web_scraper_agent(
    request: ExtractionRequest,
) -> ExtractionResponse:
    """Extrae y selecciona el contrato más completo disponible."""

    errors: list[str] = []

    try:
        static_contract = extract_static_contract(request)
    except (httpx.HTTPError, ValueError) as error:
        static_contract = None
        errors.append(str(error))

    try:
        dynamic_contract = extract_dynamic_contract(request)
    except (PlaywrightError, ValueError) as error:
        dynamic_contract = None
        errors.append(str(error))

    usable_contracts = [
        contract
        for contract in (static_contract, dynamic_contract)
        if contract is not None and has_sufficient_contract_content(contract)
    ]

    if not usable_contracts:
        detail = (
            errors[-1] if errors else "No se encontró contenido contractual utilizable."
        )
        return ExtractionResponse(
            status="error",
            error=f"No se pudo extraer el contrato: {detail}",
        )

    contract = max(usable_contracts, key=get_usable_content_length)

    return ExtractionResponse(status="success", contract=contract)
