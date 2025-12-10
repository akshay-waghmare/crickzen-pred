import pytest

import crex_scraper_python.src.crex_scraper as scraper


@pytest.fixture(autouse=True)
def fast_retry_config(monkeypatch):
    def fake_from_settings(cls, *, overrides=None):
        overrides = overrides or {}
        return cls(
            max_attempts=overrides.get("max_attempts", 3),
            base_delay=overrides.get("base_delay", 0.0),
            max_delay=overrides.get("max_delay", 0.0),
            jitter=overrides.get("jitter", 0.0),
            retry_exceptions=overrides.get("retry_exceptions", (Exception,)),
            logger=overrides.get("logger"),
        )

    monkeypatch.setattr(scraper.RetryConfig, "from_settings", classmethod(fake_from_settings))
    yield


def test_run_with_retry_succeeds_after_transient_failure(monkeypatch):
    attempts = []
    recorded_operations = []

    def flaky_operation():
        attempts.append("call")
        if len(attempts) == 1:
            raise Exception("temporary failure")
        return "ok"

    monkeypatch.setattr(scraper, "record_scraper_retry", recorded_operations.append)

    result = scraper._run_with_retry("page.goto", flaky_operation)

    assert result == "ok"
    assert attempts == ["call", "call"]
    assert recorded_operations == ["page.goto"]


def test_run_with_retry_raises_after_exhaustion(monkeypatch):
    recorded_operations = []

    def failing_operation():
        raise Exception("persistent failure")

    monkeypatch.setattr(scraper, "record_scraper_retry", recorded_operations.append)

    with pytest.raises(scraper.RetryError):
        scraper._run_with_retry("page.goto", failing_operation)

    # With three attempts the retry hook fires twice (attempts 1 and 2).
    assert recorded_operations == ["page.goto", "page.goto"]
