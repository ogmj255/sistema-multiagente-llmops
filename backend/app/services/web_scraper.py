from datetime import UTC, datetime

import httpx
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from app.schemas.contract import (
    ContractSection,
    ExtractedContract,
    ExtractionRequest,
)

USER_AGENT = "Sistema-Multiagente-LLMOps/0.1 (proyecto-academico)"
MIN_CONTRACT_SECTIONS = 3
MIN_CONTRACT_CHARACTERS = 1_000

def has_sufficient_contract_content(
    contract: ExtractedContract,
) -> bool:
    """Comprueba si el contenido extraído tiene una extensión mínima."""

    has_enough_sections = (
        len(contract.sections) >= MIN_CONTRACT_SECTIONS
    )
    has_enough_characters = (
        len(contract.full_text.strip()) >= MIN_CONTRACT_CHARACTERS
    )

    return has_enough_sections and has_enough_characters

def parse_static_html(
    html: str,
) -> tuple[str, str, list[ContractSection], str]:
    """Obtiene el contenido principal desde un documento HTML."""

    soup = BeautifulSoup(html, "html.parser")

    for element in soup.find_all(
        ["script", "style", "noscript"]
    ):
        element.decompose()

    title = soup.title.get_text(" ", strip=True) if soup.title else "Sin título"

    language = "unknown"
    if soup.html and soup.html.get("lang"):
        language = str(soup.html.get("lang")).split("-")[0]

    main_content = soup.body

    if main_content is None:
        raise ValueError("No se encontró contenido HTML para procesar.")
    sections: list[ContractSection] = []
    current_heading: str | None = None

    for element in main_content.find_all(
        ["h1", "h2", "h3", "h4", "p", "li"]
    ):
        text = element.get_text(" ", strip=True)

        if not text:
            continue

        if element.name == "li" and element.find(["p", "li"]):
            continue

        if element.name in {"h1", "h2", "h3", "h4"}:
            current_heading = text
            continue

        sections.append(
            ContractSection(
                order=len(sections) + 1,
                heading=current_heading,
                content=text,
            )
        )

    if not sections:
        raise ValueError("No se encontraron párrafos o listas en la página.")

    full_text = "\n\n".join(section.content for section in sections)

    return title, language, sections, full_text


def extract_static_contract(request: ExtractionRequest,) -> ExtractedContract:
    """Descarga y organiza un contrato publicado como HTML estático."""

    response = httpx.get(
        str(request.url),
        follow_redirects=True,
        timeout=20.0,
        headers={"User-Agent": USER_AGENT},
    )
    response.raise_for_status()

    content_type = response.headers.get("content-type", "")
    if "text/html" not in content_type:
        raise ValueError("La dirección no contiene un documento HTML.")

    title, language, sections, full_text = parse_static_html(response.text)

    platform = request.platform or request.url.host or "unknown"

    return ExtractedContract(
        source_url=request.url,
        platform=platform,
        title=title,
        retrieved_at=datetime.now(UTC),
        extraction_method="beautiful_soup",
        language=language,
        sections=sections,
        full_text=full_text,
    )

def extract_dynamic_contract(
    request: ExtractionRequest,
) -> ExtractedContract:
    """Descarga y organiza un contrato publicado en una página dinámica."""

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(user_agent=USER_AGENT)

        page.goto(
            str(request.url),
            timeout=30_000,
        )

        html = page.content()
        browser.close()

    title, language, sections, full_text = parse_static_html(html)

    platform = request.platform or request.url.host or "unknown"

    return ExtractedContract(
        source_url=request.url,
        platform=platform,
        title=title,
        retrieved_at=datetime.now(UTC),
        extraction_method="playwright",
        language=language,
        sections=sections,
        full_text=full_text,
    )
