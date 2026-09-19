from datetime import UTC, datetime

import httpx
from bs4 import BeautifulSoup
from playwright.sync_api import (
    TimeoutError as PlaywrightTimeoutError,
)
from playwright.sync_api import sync_playwright

from app.schemas.contract import (
    ExtractedContract,
    ExtractionRequest,
)

USER_AGENT = "Sistema-Multiagente-LLMOps/0.1 (proyecto-academico)"

BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/152.0.0.0 Safari/537.36"
)

STATIC_TIMEOUT_SECONDS = 20.0
DYNAMIC_TIMEOUT_MS = 30_000
NETWORK_IDLE_TIMEOUT_MS = 10_000

MIN_VISIBLE_TEXT_CHARACTERS = 500


def get_visible_text_length(html: str) -> int:
    """Estima cuánto texto visible contiene un documento HTML."""

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    for element in soup.find_all(
        [
            "script",
            "style",
            "noscript",
            "template",
        ]
    ):
        element.decompose()

    body = soup.body

    if body is None:
        return 0

    text = " ".join(
        body.get_text(
            " ",
            strip=True,
        ).split()
    )

    return len(text)


def has_sufficient_html_content(html: str) -> bool:
    """Comprueba si el HTML estático contiene texto visible suficiente."""

    return (
        get_visible_text_length(html)
        >= MIN_VISIBLE_TEXT_CHARACTERS
    )


def extract_static_contract(
    request: ExtractionRequest,
) -> ExtractedContract:
    """Obtiene el HTML crudo mediante una solicitud HTTP."""

    response = httpx.get(
        str(request.url),
        follow_redirects=True,
        timeout=STATIC_TIMEOUT_SECONDS,
        headers={
            "User-Agent": USER_AGENT,
        },
    )

    response.raise_for_status()

    content_type = response.headers.get(
        "content-type",
        "",
    ).lower()

    if "text/html" not in content_type:
        raise ValueError(
            "La dirección no contiene un documento HTML."
        )

    html = response.text

    if not html.strip():
        raise ValueError(
            "La página devolvió un documento HTML vacío."
        )

    platform = (
        request.platform
        or request.url.host
        or "unknown"
    )

    return ExtractedContract(
        source_url=request.url,
        platform=platform,
        retrieved_at=datetime.now(UTC),
        extraction_method="httpx",
        raw_html=html,
    )


def extract_dynamic_contract(
    request: ExtractionRequest,
) -> ExtractedContract:
    """Obtiene el HTML renderizado mediante Playwright."""

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()

        try:
            page = browser.new_page(
                user_agent=BROWSER_USER_AGENT,
            )

            navigation_response = page.goto(
                str(request.url),
                wait_until="domcontentloaded",
                timeout=DYNAMIC_TIMEOUT_MS,
            )

            if navigation_response is None:
                raise ValueError(
                    "La navegación no devolvió una respuesta HTTP."
                )

            if not navigation_response.ok:
                raise ValueError(
                    "La página devolvió un estado HTTP "
                    f"{navigation_response.status}."
                )

            try:
                page.wait_for_load_state(
                    "networkidle",
                    timeout=NETWORK_IDLE_TIMEOUT_MS,
                )
            except PlaywrightTimeoutError:
                pass

            html = page.content()

        finally:
            browser.close()

    if not html.strip():
        raise ValueError(
            "Playwright devolvió un documento HTML vacío."
        )

    platform = (
        request.platform
        or request.url.host
        or "unknown"
    )

    return ExtractedContract(
        source_url=request.url,
        platform=platform,
        retrieved_at=datetime.now(UTC),
        extraction_method="playwright",
        raw_html=html,
    )
