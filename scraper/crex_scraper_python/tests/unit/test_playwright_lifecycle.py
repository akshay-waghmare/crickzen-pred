import pytest

from crex_scraper_python.src.crex_scraper import (
    managed_browser,
    managed_context,
    managed_page,
)


class DummyCloseable:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class DummyPlaywright:
    class _Chromium:
        def __init__(self, browser):
            self._browser = browser

        def launch(self, **launch_kwargs):  # pragma: no cover - kwargs unused in dummy
            return self._browser

    def __init__(self, browser):
        self.chromium = self._Chromium(browser)


class DummyBrowser(DummyCloseable):
    def __init__(self, context):
        super().__init__()
        self._context = context

    def new_context(self, **context_kwargs):  # pragma: no cover - kwargs unused in dummy
        return self._context


class DummyContext(DummyCloseable):
    def __init__(self, page):
        super().__init__()
        self._page = page

    def new_page(self, **page_kwargs):  # pragma: no cover - kwargs unused in dummy
        return self._page


class DummyPage(DummyCloseable):
    pass


def test_managed_browser_closes_on_exit():
    browser = DummyBrowser(DummyContext(DummyPage()))
    playwright = DummyPlaywright(browser)

    with managed_browser(playwright):
        assert not browser.closed

    assert browser.closed


def test_managed_browser_closes_on_error():
    browser = DummyBrowser(DummyContext(DummyPage()))
    playwright = DummyPlaywright(browser)

    with pytest.raises(RuntimeError):
        with managed_browser(playwright):
            raise RuntimeError("boom")

    assert browser.closed


def test_managed_context_closes_on_exit():
    page = DummyPage()
    context = DummyContext(page)
    browser = DummyBrowser(context)

    with managed_context(browser):
        assert not context.closed

    assert context.closed


def test_managed_context_closes_on_error():
    page = DummyPage()
    context = DummyContext(page)
    browser = DummyBrowser(context)

    with pytest.raises(RuntimeError):
        with managed_context(browser):
            raise RuntimeError("fail context")

    assert context.closed


def test_managed_page_closes_on_exit():
    page = DummyPage()
    context = DummyContext(page)

    with managed_page(context):
        assert not page.closed

    assert page.closed


def test_managed_page_closes_on_error():
    page = DummyPage()
    context = DummyContext(page)

    with pytest.raises(RuntimeError):
        with managed_page(context):
            raise RuntimeError("fail page")

    assert page.closed
