from io import StringIO

import pytest

from src.config import ScraperSettings
from crex_scraper_python.logging_config import setup_logging
from crex_scraper_python.parsers import (
    SELECTORS,
    SelectorResolutionError,
    extract_match_href,
    select_all,
    select_first,
)


class FakeHandle:
    """Minimal stub matching the playwright ElementHandle interface."""

    def __init__(self, selectors):
        self._selectors = selectors

    def query_selector(self, selector):
        return self._selectors.get(selector)

    def query_selector_all(self, selector):
        return self._selectors.get(selector, [])

    def get_attribute(self, attribute):  # pragma: no cover - passthrough for nested handles
        return getattr(self, attribute, None)


class FakeAnchor(FakeHandle):
    def __init__(self, href):
        super().__init__({})
        self.href = href

    def get_attribute(self, attribute):
        if attribute == "href":
            return self.href
        return super().get_attribute(attribute)


@pytest.fixture(autouse=True)
def configure_logging():
    stream = StringIO()
    setup_logging(
        ScraperSettings(
            log_level="INFO",
            log_format="json",
        ),
        stream=stream,
    )
    try:
        yield stream
    finally:
        stream.close()


def test_select_first_uses_primary_selector():
    handle = FakeHandle({SELECTORS["live_match_badge"][0]: object()})

    result = select_first(handle, "live_match_badge", required=True)

    assert result is not None


def test_select_first_falls_back_and_logs(configure_logging):
    fallback_selector = SELECTORS["live_match_badge"][1]
    handle = FakeHandle({fallback_selector: object()})

    result = select_first(handle, "live_match_badge", required=True, log_context={"url": "https://crex.com"})

    assert result is not None
    log_output = configure_logging.getvalue()
    assert "selector.fallback.hit" in log_output


def test_select_all_returns_results_from_fallback_selector():
    fallback_selector = SELECTORS["live_match_badge"][2]
    expected = [object(), object()]
    handle = FakeHandle({fallback_selector: expected})

    result = select_all(handle, "live_match_badge", required=True)

    assert result == expected


def test_select_all_raises_when_all_selectors_fail():
    handle = FakeHandle({})

    with pytest.raises(SelectorResolutionError):
        select_all(handle, "live_match_badge", required=True)


def test_extract_match_href_uses_fallback_anchor_selector(configure_logging):
    fallback_selector = SELECTORS["live_match_anchor"][1]
    expected_href = "/match/123"
    handle = FakeHandle({fallback_selector: FakeAnchor(expected_href)})

    href = extract_match_href(handle, log_context={"url": "https://crex.com"})

    assert href == expected_href
    assert "selector.fallback.hit" in configure_logging.getvalue()


def test_extract_match_href_raises_when_href_missing():
    primary_selector = SELECTORS["live_match_anchor"][0]
    handle = FakeHandle({primary_selector: FakeAnchor(href=None)})

    with pytest.raises(SelectorResolutionError):
        extract_match_href(handle)
