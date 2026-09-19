from unittest.mock import MagicMock

import pytest
from app.schemas.contract import ExtractionRequest
from app.services import web_scraper
from app.services.web_scraper import (
    get_visible_text_length,
    has_sufficient_html_content,
)


def create_request() -> ExtractionRequest:
    return ExtractionRequest(
        url="https://example.com/terms",
        platform="Example",
    )


def test_visible_text_ignores_technical_elements() -> None:
    html = """
    <html>
        <body>
            <script>ignored_script_content()</script>
            <style>.hidden { display: none; }</style>
            <noscript>Ignored noscript content.</noscript>
            <template>Ignored template content.</template>
            <p>Visible contractual text.</p>
        </body>
    </html>
    """

    assert get_visible_text_length(html) == len(
        "Visible contractual text."
    )


def test_accept_sufficient_static_html() -> None:
    html = (
        "<html><body><main><p>"
        + ("A" * 600)
        + "</p></main></body></html>"
    )

    assert has_sufficient_html_content(html) is True


def test_reject_insufficient_static_html() -> None:
    html = """
    <html>
        <body>
            <p>Loading...</p>
        </body>
    </html>
    """

    assert has_sufficient_html_content(html) is False


def test_reject_html_without_body_as_sufficient() -> None:
    html = """
    <html>
        <head>
            <title>Terms</title>
        </head>
    </html>
    """

    assert has_sufficient_html_content(html) is False


def test_static_extraction_returns_raw_html(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = create_request()

    html = """
    <html lang="en">
        <body>
            <nav>Navigation remains untouched.</nav>
            <main>
                <p>Contractual content.</p>
            </main>
            <script>raw_script_marker()</script>
        </body>
    </html>
    """

    response = MagicMock()
    response.headers = {
        "content-type": "text/html; charset=utf-8",
    }
    response.text = html

    monkeypatch.setattr(
        web_scraper.httpx,
        "get",
        lambda *args, **kwargs: response,
    )

    contract = web_scraper.extract_static_contract(
        request
    )

    assert contract.extraction_method == "httpx"
    assert contract.raw_html == html
    assert "Navigation remains untouched." in contract.raw_html
    assert "raw_script_marker()" in contract.raw_html

    response.raise_for_status.assert_called_once_with()


def test_static_extraction_rejects_non_html(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = create_request()

    response = MagicMock()
    response.headers = {
        "content-type": "application/json",
    }
    response.text = '{"status": "ok"}'

    monkeypatch.setattr(
        web_scraper.httpx,
        "get",
        lambda *args, **kwargs: response,
    )

    with pytest.raises(
        ValueError,
        match="documento HTML",
    ):
        web_scraper.extract_static_contract(
            request
        )


def test_static_extraction_rejects_empty_html(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = create_request()

    response = MagicMock()
    response.headers = {
        "content-type": "text/html",
    }
    response.text = "   "

    monkeypatch.setattr(
        web_scraper.httpx,
        "get",
        lambda *args, **kwargs: response,
    )

    with pytest.raises(
        ValueError,
        match="HTML",
    ):
        web_scraper.extract_static_contract(
            request
        )


def test_dynamic_extraction_rejects_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = create_request()

    playwright_manager = MagicMock()
    playwright = playwright_manager.__enter__.return_value

    browser = playwright.chromium.launch.return_value
    page = browser.new_page.return_value

    navigation_response = MagicMock()
    navigation_response.ok = False
    navigation_response.status = 403

    page.goto.return_value = navigation_response

    monkeypatch.setattr(
        web_scraper,
        "sync_playwright",
        lambda: playwright_manager,
    )

    with pytest.raises(
        ValueError,
        match="HTTP 403",
    ):
        web_scraper.extract_dynamic_contract(
            request
        )

    page.content.assert_not_called()
    browser.close.assert_called_once_with()


def test_dynamic_extraction_returns_rendered_raw_html(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = create_request()

    rendered_html = """
    <html>
        <body>
            <main>
                <p>Rendered contractual content.</p>
            </main>
            <script>rendered_script_marker()</script>
        </body>
    </html>
    """

    playwright_manager = MagicMock()
    playwright = playwright_manager.__enter__.return_value

    browser = playwright.chromium.launch.return_value
    page = browser.new_page.return_value

    navigation_response = MagicMock()
    navigation_response.ok = True
    navigation_response.status = 200

    page.goto.return_value = navigation_response
    page.content.return_value = rendered_html

    monkeypatch.setattr(
        web_scraper,
        "sync_playwright",
        lambda: playwright_manager,
    )

    contract = web_scraper.extract_dynamic_contract(
        request
    )

    assert contract.extraction_method == "playwright"
    assert contract.raw_html == rendered_html
    assert "rendered_script_marker()" in contract.raw_html

    page.content.assert_called_once_with()
    browser.close.assert_called_once_with()
