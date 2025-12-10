from prometheus_client import generate_latest
from prometheus_client.parser import text_string_to_metric_families

from crex_scraper_python import monitoring
from src.config import ScraperSettings
from src.core.scraper_context import ScraperContext


def setup_function() -> None:
    monitoring.reset_metrics_for_tests()


def _collect_metrics():
    metrics_text = generate_latest(monitoring.METRIC_REGISTRY).decode("utf-8")
    return {family.name: family for family in text_string_to_metric_families(metrics_text)}


def test_record_update_and_error_metrics():
    monitoring.record_scraper_update("match-xyz", latency_seconds=1.25)
    monitoring.record_scraper_error("match-xyz", "TimeoutError")
    monitoring.record_scraper_retry("page.goto")
    monitoring.record_scraper_retry("page.goto")
    monitoring.set_scraper_memory("match-xyz", 1_048_576)
    monitoring.set_data_staleness("match-xyz", 42.0)
    monitoring.set_active_scrapers(2)

    families = _collect_metrics()

    updates_family = families["scraper_updates_total"]
    assert any(sample.labels.get("match_id") == "match-xyz" and sample.value == 1.0 for sample in updates_family.samples)

    errors_family = families["scraper_errors_total"]
    assert any(
        sample.labels.get("match_id") == "match-xyz"
        and sample.labels.get("error_type") == "TimeoutError"
        and sample.value == 1.0
        for sample in errors_family.samples
    )

    latency_family = families["scraper_update_latency_seconds"]
    count_sample = next(
        sample
        for sample in latency_family.samples
        if sample.name.endswith("_count") and sample.labels.get("match_id") == "match-xyz"
    )
    assert count_sample.value == 1.0

    active_family = families["active_scrapers_count"]
    assert active_family.samples[0].value == 2.0

    staleness_family = families["data_staleness_seconds"]
    staleness_sample = next(
        sample
        for sample in staleness_family.samples
        if sample.labels.get("match_id") == "match-xyz"
    )
    assert staleness_sample.value == 42.0

    retries_family = families["scraper_retry_attempts_total"]
    retry_sample = next(
        sample
        for sample in retries_family.samples
        if sample.labels.get("operation") == "page.goto"
    )
    assert retry_sample.value == 2.0


def test_update_context_metrics_reflects_context_state():
    context = ScraperContext(match_id="match-metric", url="https://example.com/match")
    context.update_memory_bytes(2_097_152)
    monitoring.update_context_metrics(context)

    families = _collect_metrics()
    memory_family = families["scraper_memory_bytes"]
    memory_sample = next(
        sample
        for sample in memory_family.samples
        if sample.labels.get("match_id") == "match-metric"
    )
    assert memory_sample.value == 2_097_152


def test_clear_scraper_gauges_removes_series():
    monitoring.set_scraper_memory("match-old", 512)
    monitoring.set_data_staleness("match-old", 5.0)
    monitoring.clear_scraper_gauges("match-old")

    families = _collect_metrics()
    memory_samples = families.get("scraper_memory_bytes", None)
    if memory_samples:
        assert all(sample.labels.get("match_id") != "match-old" for sample in memory_samples.samples)
    staleness_samples = families.get("data_staleness_seconds", None)
    if staleness_samples:
        assert all(sample.labels.get("match_id") != "match-old" for sample in staleness_samples.samples)


def test_ensure_metrics_server_runs_once(monkeypatch):
    calls = []

    def fake_start_http_server(port: int, addr: str, registry):
        calls.append((port, addr, registry))

    monkeypatch.setattr(monitoring, "start_http_server", fake_start_http_server)

    settings = ScraperSettings(prometheus_port=8081)
    first = monitoring.ensure_metrics_server(settings)
    second = monitoring.ensure_metrics_server(settings)

    assert first is True
    assert second is False
    assert calls == [(8081, settings.prometheus_host, monitoring.METRIC_REGISTRY)]
