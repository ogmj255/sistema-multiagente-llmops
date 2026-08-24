from time import perf_counter, sleep

from app.agents.preprocessor_agent import run_preprocessor_agent
from app.agents.web_scraper_agent import run_web_scraper_agent
from app.schemas.contract import ExtractionRequest

SOURCES = [
    (
        "Baja",
        "Slack",
        "https://slack.com/terms-of-service/user",
    ),
    (
        "Media",
        "Dropbox",
        "https://www.dropbox.com/terms",
    ),
    (
        "Media",
        "GitHub",
        (
            "https://docs.github.com/site-policy/"
            "github-terms/github-terms-of-service"
        ),
    ),
    (
        "Alta",
        "Atlassian",
        (
            "https://www.atlassian.com/legal/"
            "atlassian-customer-agreement"
        ),
    ),
    (
        "Alta",
        "HubSpot",
        "https://legal.hubspot.com/terms-of-service",
    ),
]


def main() -> None:
    """Valida el preprocesador con contratos de complejidad variable."""

    completed = 0

    for complexity, platform, url in SOURCES:
        started = perf_counter()
        print(f"\nProcesando: {platform} ({complexity})")

        extraction = run_web_scraper_agent(
            ExtractionRequest(url=url, platform=platform)
        )

        if extraction.contract is None:
            print("Estado scraper: error")
            print("Error:", extraction.error)
            continue

        preprocessing = run_preprocessor_agent(
            extraction.contract
        )

        print("Estado scraper:", extraction.status)
        print("Método:", extraction.contract.extraction_method)
        print("Secciones:", len(extraction.contract.sections))

        if preprocessing.result is None:
            print("Estado preprocesador: error")
            print("Error:", preprocessing.error)
        else:
            result = preprocessing.result
            completed += 1
            print("Estado preprocesador:", preprocessing.status)
            print("Cláusulas:", len(result.clauses))
            print("Eliminados:", len(result.removed_blocks))
            print("Caracteres limpios:", len(result.cleaned_text))

        print(
            "Tiempo:",
            round(perf_counter() - started, 2),
            "segundos",
        )
        sleep(2)

    print(f"\nResumen: {completed} de {len(SOURCES)} procesados.")


if __name__ == "__main__":
    main()