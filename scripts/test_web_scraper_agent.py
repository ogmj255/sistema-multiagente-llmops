from time import sleep

from app.agents.web_scraper_agent import run_web_scraper_agent
from app.schemas.contract import ExtractionRequest


def main() -> None:
    """Prueba el agente con cinco contratos públicos de plataformas SaaS."""

    sources = [
        ExtractionRequest(
            url=(
                "https://docs.github.com/site-policy/"
                "github-terms/github-terms-of-service"
            ),
            platform="GitHub",
        ),
        ExtractionRequest(
            url="https://slack.com/terms-of-service/user",
            platform="Slack",
        ),
        ExtractionRequest(
            url="https://www.dropbox.com/terms",
            platform="Dropbox",
        ),
        ExtractionRequest(
            url=(
                "https://www.atlassian.com/legal/"
                "atlassian-customer-agreement"
            ),
            platform="Atlassian",
        ),
        ExtractionRequest(
            url="https://legal.hubspot.com/terms-of-service",
            platform="HubSpot",
        ),
    ]

    successful_extractions = 0

    for request in sources:
        print("\nProcesando:", request.platform)

        response = run_web_scraper_agent(request)

        if response.contract is not None:
            successful_extractions += 1

            print("Estado:", response.status)
            print("Título:", response.contract.title)
            print("Método:", response.contract.extraction_method)
            print("Idioma:", response.contract.language)
            print("Secciones:", len(response.contract.sections))
            print("Caracteres:", len(response.contract.full_text))
        else:
            print("Estado:", response.status)
            print("Error:", response.error)

        sleep(2)

    print("\nResumen:", successful_extractions, "de", len(sources))
    print("extracciones completadas correctamente.")


if __name__ == "__main__":
    main()
