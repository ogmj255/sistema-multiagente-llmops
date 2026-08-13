from app.schemas.contract import ExtractionRequest
from app.services.web_scraper import extract_dynamic_contract


def main() -> None:
    """Prueba la extracción de un contrato mediante Playwright."""

    request = ExtractionRequest(
        url="https://slack.com/terms-of-service/user",
        platform="Slack",
    )

    contract = extract_dynamic_contract(request)
    first_section = contract.sections[0]

    print("Plataforma:", contract.platform)
    print("Título:", contract.title)
    print("Idioma:", contract.language)
    print("Método:", contract.extraction_method)
    print("Secciones extraídas:", len(contract.sections))
    print("Caracteres extraídos:", len(contract.full_text))
    print("Primer encabezado:", first_section.heading)
    print("Primer contenido:", first_section.content[:200])


if __name__ == "__main__":
    main()
