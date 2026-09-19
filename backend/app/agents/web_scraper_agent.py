import httpx
from playwright.sync_api import Error as PlaywrightError

from app.schemas.contract import ExtractionRequest, ExtractionResponse
from app.services.web_scraper import (
    extract_dynamic_contract,
    extract_static_contract,
    has_sufficient_html_content,
)


def run_web_scraper_agent(
    request: ExtractionRequest,
) -> ExtractionResponse:
    """Obtiene el HTML del contrato mediante extracción estática o dinámica."""

    errors: list[str] = []

    try:
        static_contract = extract_static_contract(
            request
        )

        if has_sufficient_html_content(
            static_contract.raw_html
        ):
            return ExtractionResponse(
                status="success",
                contract=static_contract,
            )

        errors.append(
            "El HTML estático no contiene suficiente texto visible."
        )

    except (httpx.HTTPError, ValueError) as error:
        errors.append(str(error))

    try:
        dynamic_contract = extract_dynamic_contract(
            request
        )

        if has_sufficient_html_content(
            dynamic_contract.raw_html
        ):
            return ExtractionResponse(
                status="success",
                contract=dynamic_contract,
            )

        errors.append(
            "El HTML din?mico no contiene suficiente texto visible."
        )

    except (PlaywrightError, ValueError) as error:
        errors.append(str(error))

    detail = (
        errors[-1]
        if errors
        else "No se pudo obtener el documento HTML."
    )

    return ExtractionResponse(
        status="error",
        error=f"No se pudo extraer el HTML: {detail}",
    )
