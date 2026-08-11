from app.schemas.contract import ExtractionRequest
from app.services.web_scraper import extract_static_contract


def main() -> None:
    request = ExtractionRequest(
        url=(
            "https://docs.github.com/site-policy/"
            "github-terms/github-terms-of-service"
        ),
        platform="GitHub",
    )

    contract = extract_static_contract(request)

    print("Plataforma:", contract.platform)
    print("Título:", contract.title)
    print("Idioma:", contract.language)
    print("Método:", contract.extraction_method)
    print("Secciones extraídas:", len(contract.sections))
    print("Caracteres extraídos:", len(contract.full_text))
    print("Primer encabezado:", contract.sections[0].heading)
    print("Primer contenido:", contract.sections[0].content[:200])


if __name__ == "__main__":
    main()
