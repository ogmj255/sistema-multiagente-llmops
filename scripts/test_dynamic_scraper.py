from app.schemas.contract import ExtractionRequest
from app.services.web_scraper import extract_dynamic_contract


def main() -> None:
    """Prueba la obtencion de HTML renderizado mediante Playwright."""

    request = ExtractionRequest(
        url="https://slack.com/terms-of-service/user",
        platform="Slack",
    )

    contract = extract_dynamic_contract(
        request
    )

    print(
        "Plataforma:",
        contract.platform,
    )
    print(
        "Metodo:",
        contract.extraction_method,
    )
    print(
        "URL:",
        contract.source_url,
    )
    print(
        "Caracteres HTML:",
        len(contract.raw_html),
    )
    print(
        "Inicio del HTML:",
        contract.raw_html[:500],
    )


if __name__ == "__main__":
    main()
