"""Automatic CREX match discovery and prediction startup."""

from __future__ import annotations

import asyncio
import logging
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, time, timezone, tzinfo
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse
from zoneinfo import ZoneInfo

import httpx

from app.config import (
    LEAGUE_CONFIGS,
    Settings,
    detect_generic_format_from_url,
    detect_league_from_url,
    get_settings,
)
from app.prediction_manager import PredictionManager

logger = logging.getLogger(__name__)

SYSTEM_USER_ID = "system:auto-scheduler"
CREX_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


@dataclass(frozen=True)
class MatchCandidate:
    """A CREX match URL that can be started by the scheduler."""

    url: str
    league_key: str
    source: str
    label: str = ""
    is_live: bool = False


class AutoPredictionScheduler:
    """Poll CREX/current configured URLs and start live prediction processes."""

    def __init__(self, manager: PredictionManager, settings: Settings):
        self.manager = manager
        self.settings = settings
        self._stop_event = asyncio.Event()
        self._last_checked_at: datetime | None = None
        self._last_error: str | None = None
        self._last_candidates: list[MatchCandidate] = []
        self._last_started: list[dict[str, Any]] = []

    async def run_forever(self) -> None:
        """Run until cancelled by FastAPI lifespan shutdown."""
        logger.info("Auto prediction scheduler started")
        try:
            while not self._stop_event.is_set():
                await self.check_once()
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=max(30, self.settings.AUTO_DISCOVERY_INTERVAL_SECONDS),
                    )
                except asyncio.TimeoutError:
                    pass
        except asyncio.CancelledError:
            raise
        finally:
            logger.info("Auto prediction scheduler stopped")

    def stop(self) -> None:
        self._stop_event.set()

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.settings.AUTO_PREDICTIONS_ENABLED,
            "league": self.settings.AUTO_LEAGUE_KEY,
            "leagues": self._target_leagues(),
            "running": not self._stop_event.is_set(),
            "last_checked_at": self._last_checked_at.isoformat() if self._last_checked_at else None,
            "last_error": self._last_error,
            "last_candidates": [
                {
                    "url": c.url,
                    "league": c.league_key,
                    "source": c.source,
                    "label": c.label,
                    "is_live": c.is_live,
                }
                for c in self._last_candidates
            ],
            "last_started": self._last_started[-10:],
        }

    async def check_once(self) -> list[MatchCandidate]:
        """Discover candidates and start eligible predictions."""
        self._last_checked_at = datetime.now(tz=self._timezone())
        self._last_error = None

        try:
            self.manager.cleanup_expired(self.settings)
            candidates = await self.discover_candidates()
            self._last_candidates = candidates
            for candidate in candidates:
                if not self._should_start(candidate):
                    continue
                if self.manager.find_active_by_url(candidate.url, candidate.league_key):
                    continue
                try:
                    pred = self.manager.start_match(
                        user_id=SYSTEM_USER_ID,
                        match_url=candidate.url,
                        league_key=candidate.league_key,
                    )
                    started = {
                        "prediction_id": pred.id,
                        "url": candidate.url,
                        "league": candidate.league_key,
                        "started_at": datetime.now(tz=self._timezone()).isoformat(),
                        "source": candidate.source,
                    }
                    self._last_started.append(started)
                    logger.info("Auto-started prediction %s for %s", pred.id, candidate.url)
                except Exception as exc:
                    logger.warning("Auto-start failed for %s: %s", candidate.url, exc)
                    self._last_error = str(exc)
            return candidates
        except Exception as exc:
            self._last_error = str(exc)
            logger.warning("Auto scheduler check failed: %s", exc)
            return []

    async def discover_candidates(self) -> list[MatchCandidate]:
        candidates: list[MatchCandidate] = []

        # The scraper owns the finite, selected live slate. Prefer that
        # contract so prediction coverage exactly matches the five matches
        # the stack is already scraping; CREX page discovery is only fallback.
        scraper_candidates = await self._discover_from_scraper()
        if scraper_candidates:
            return _dedupe_candidates(scraper_candidates)

        async with httpx.AsyncClient(
            headers=CREX_HEADERS,
            timeout=httpx.Timeout(20.0),
            follow_redirects=True,
        ) as client:
            for url in _split_setting_list(self.settings.AUTO_MATCH_URLS):
                league_key = detect_league_from_url(url) or self.settings.AUTO_LEAGUE_KEY
                if league_key not in LEAGUE_CONFIGS:
                    continue
                candidates.append(await self._candidate_for_direct_url(client, url, league_key))

            if self.settings.AUTO_DISCOVER_FROM_CREX:
                all_mode = any(item.upper() == "ALL" for item in re.split(r"\s*,\s*", self.settings.AUTO_LEAGUE_KEYS or "") if item.strip())
                discovery_leagues: list[str | None] = [None] if all_mode else self._target_leagues()
                discovery_urls = self._discovery_urls() if all_mode else [
                    url for league_key in self._target_leagues() for url in self._discovery_urls(league_key)
                ]
                for league_key in discovery_leagues:
                    for source_url in dict.fromkeys(discovery_urls):
                        try:
                            response = await client.get(source_url)
                            response.raise_for_status()
                        except Exception as exc:
                            logger.debug("Could not fetch CREX discovery page %s: %s", source_url, exc)
                            continue
                        extracted = extract_crex_match_candidates(
                            response.text,
                            base_url=str(response.url),
                            target_league_key=league_key,
                            source=source_url,
                        )
                        if self.settings.AUTO_DISCOVERY_RENDER_JS:
                            rendered_html = await _fetch_rendered_crex_html(source_url)
                            if rendered_html:
                                rendered_candidates = extract_crex_match_candidates(
                                    rendered_html,
                                    base_url=source_url,
                                    target_league_key=league_key,
                                    source=source_url,
                                )
                                extracted = _dedupe_candidates(extracted + rendered_candidates)
                        allowed_leagues = set(self._target_leagues())
                        candidates.extend(
                            candidate for candidate in extracted
                            if candidate.league_key in allowed_leagues
                        )

        return _dedupe_candidates(candidates)

    async def _discover_from_scraper(self) -> list[MatchCandidate]:
        base = (self.settings.AUTO_SCRAPER_URL or "").strip().rstrip("/")
        if not base:
            return []
        try:
            async with httpx.AsyncClient(headers=CREX_HEADERS, timeout=httpx.Timeout(10.0)) as client:
                response = await client.get(f"{base}/prediction-candidates")
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:
            logger.debug("Could not fetch scraper prediction candidates: %s", exc)
            return []

        candidates: list[MatchCandidate] = []
        for item in payload.get("matches", []) if isinstance(payload, dict) else []:
            if isinstance(item, str):
                url, is_live, label = item, True, ""
            elif isinstance(item, dict):
                url = item.get("url") or item.get("matchUrl") or item.get("match_url")
                is_live = bool(item.get("is_live", True))
                label = str(item.get("label") or "")
            else:
                continue
            league_key = detect_league_from_url(url or "") or detect_generic_format_from_url(url or "")
            if not url or not league_key or league_key not in self._target_leagues():
                continue
            candidates.append(MatchCandidate(
                url=_normalize_crex_url(url),
                league_key=league_key,
                source="scraper:selected",
                label=label or url,
                is_live=is_live,
            ))
        return candidates

    async def _candidate_for_direct_url(
        self,
        client: httpx.AsyncClient,
        url: str,
        league_key: str,
    ) -> MatchCandidate:
        label = url
        is_live = True
        try:
            response = await client.get(url)
            if response.status_code < 400:
                label = _page_title_or_text(response.text) or url
                is_live = _looks_live(response.text)
        except Exception:
            pass
        return MatchCandidate(
            url=_normalize_crex_url(url),
            league_key=league_key,
            source="env:AUTO_MATCH_URLS",
            label=label,
            is_live=is_live,
        )

    def _target_leagues(self) -> list[str]:
        # League keys can contain spaces (for example "ODI Women"); unlike
        # URLs, this setting is comma-delimited rather than whitespace-delimited.
        configured = [item.strip() for item in re.split(r"\s*,\s*", self.settings.AUTO_LEAGUE_KEYS or "") if item.strip()]
        if any(item.upper() == "ALL" for item in configured):
            leagues = list(LEAGUE_CONFIGS.keys())
        else:
            leagues = configured or [self.settings.AUTO_LEAGUE_KEY]
        excluded = {
            item.strip() for item in re.split(r"\s*,\s*", self.settings.AUTO_EXCLUDE_LEAGUES or "") if item.strip()
        }
        leagues = [league for league in leagues if league not in excluded]
        return [league for league in dict.fromkeys(leagues) if league in LEAGUE_CONFIGS]

    def _discovery_urls(self, league_key: str | None = None) -> list[str]:
        urls = _split_setting_list(self.settings.AUTO_DISCOVERY_URLS)
        cfg = LEAGUE_CONFIGS.get(league_key or self.settings.AUTO_LEAGUE_KEY, {})
        series_url = cfg.get("series_url")
        if isinstance(series_url, str) and series_url:
            urls.append(series_url)
        urls.extend(["https://crex.com/cricket-live-score", "https://crex.com/live-matches"])
        return list(dict.fromkeys(urls))

    def _should_start(self, candidate: MatchCandidate) -> bool:
        if candidate.source == "env:AUTO_MATCH_URLS":
            return True
        if candidate.is_live:
            return True
        now = datetime.now(tz=self._timezone())
        return self._inside_local_start_window() and _label_mentions_date(candidate.label, now)

    def _inside_local_start_window(self) -> bool:
        now = datetime.now(tz=self._timezone()).time()
        start = _parse_hhmm(self.settings.AUTO_START_NOT_BEFORE_LOCAL, default=time(17, 0))
        end = _parse_hhmm(self.settings.AUTO_START_NOT_AFTER_LOCAL, default=time(23, 59))
        if start <= end:
            return start <= now <= end
        return now >= start or now <= end

    def _timezone(self) -> tzinfo:
        try:
            return ZoneInfo(self.settings.AUTO_TIMEZONE)
        except Exception:
            return timezone.utc


def extract_crex_match_candidates(
    html: str,
    *,
    base_url: str,
    target_league_key: str | None,
    source: str,
) -> list[MatchCandidate]:
    """Extract CREX match URLs from server-rendered anchors."""
    results: list[MatchCandidate] = []
    for href, body in re.findall(
        r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",
        html or "",
        flags=re.IGNORECASE | re.DOTALL,
    ):
        absolute_url = _normalize_crex_url(urljoin(base_url, unescape(href)))
        if not _is_crex_match_url(absolute_url):
            continue
        if _is_test_match_url(absolute_url):
            continue
        league_key = detect_league_from_url(absolute_url) or detect_generic_format_from_url(absolute_url)
        if not league_key:
            continue
        if target_league_key and league_key != target_league_key:
            continue
        label = _strip_tags(body)
        if _looks_finished(label):
            continue
        results.append(
            MatchCandidate(
                url=absolute_url,
                league_key=league_key,
                source=source,
                label=label,
                is_live=_looks_live(label),
            )
        )
    return results


def _split_setting_list(value: str) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in re.split(r"[\s,]+", value) if part.strip()]


def _dedupe_candidates(candidates: list[MatchCandidate]) -> list[MatchCandidate]:
    seen: set[str] = set()
    deduped: list[MatchCandidate] = []
    for candidate in candidates:
        key = f"{candidate.league_key}:{_normalize_crex_url(candidate.url).lower()}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def _normalize_crex_url(url: str) -> str:
    parsed = urlparse((url or "").strip())
    if not parsed.scheme:
        parsed = urlparse(urljoin("https://crex.com", url))
    path = parsed.path.rstrip("/")
    return urlunparse((parsed.scheme or "https", parsed.netloc, path, "", "", ""))


def _is_crex_match_url(url: str) -> bool:
    url_lower = url.lower()
    return (
        "crex.com" in url_lower
        and (
            "/cricket-live-score/" in url_lower
            or "/scoreboard/" in url_lower
        )
        and (
            "match-updates" in url_lower
            or "/scoreboard/" in url_lower
        )
    )


def _is_test_match_url(url: str) -> bool:
    """Exclude red-ball Test fixtures from white-ball prediction discovery."""
    return bool(re.search(r"(?:^|[-_/])test(?:[-_/]|$)|test-match|test-series", url.lower()))


def _strip_tags(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _page_title_or_text(html: str) -> str:
    title = re.search(r"<title[^>]*>(.*?)</title>", html or "", flags=re.IGNORECASE | re.DOTALL)
    if title:
        return _strip_tags(title.group(1))
    return _strip_tags(html)[:200]


def _looks_live(text: str) -> bool:
    clean = f" {_strip_tags(text).lower()} "
    if _looks_finished(clean):
        return False
    return bool(re.search(r"\blive\b|\bopt\s+to\s+bat\b|\bruns?\s+needed\b|\bneed\s+\d+\b", clean)) or bool(
        re.search(r"\b\d+[-/]\d+\s+\d+\.\d+\b", clean)
    )


def _looks_finished(text: str) -> bool:
    clean = f" {_strip_tags(text).lower()} "
    has_finished_label = bool(re.search(r"\b(won|abandoned|no result|finished|complete)\b", clean))
    has_explicit_live_signal = bool(re.search(r"\blive\b|\bopt\s+to\s+bat\b|\bruns?\s+needed\b|\bneed\s+\d+\b", clean))
    return has_finished_label and not has_explicit_live_signal


def _parse_hhmm(value: str, *, default: time) -> time:
    match = re.match(r"^\s*(\d{1,2}):(\d{2})\s*$", value or "")
    if not match:
        return default
    hour = max(0, min(23, int(match.group(1))))
    minute = max(0, min(59, int(match.group(2))))
    return time(hour, minute)


def _label_mentions_date(label: str, when: datetime) -> bool:
    """Return True when a CREX card label appears to be for this local date."""
    clean = _strip_tags(label).lower()
    if not clean:
        return False
    months = {
        1: ("jan", "january"),
        2: ("feb", "february"),
        3: ("mar", "march"),
        4: ("apr", "april"),
        5: ("may", "may"),
        6: ("jun", "june"),
        7: ("jul", "july"),
        8: ("aug", "august"),
        9: ("sep", "september"),
        10: ("oct", "october"),
        11: ("nov", "november"),
        12: ("dec", "december"),
    }
    day = when.day
    for month in months[when.month]:
        if re.search(rf"\b{re.escape(month)}\s+0?{day}\b", clean):
            return True
        if re.search(rf"\b0?{day}\s+{re.escape(month)}\b", clean):
            return True
    return False


async def _fetch_rendered_crex_html(url: str) -> str:
    """Render a CREX page and serialize anchors for client-rendered schedules."""
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as playwright:
            executable = _browser_executable()
            launch_kwargs = {"headless": True}
            if executable:
                launch_kwargs["executable_path"] = executable
            browser = await playwright.chromium.launch(**launch_kwargs)
            try:
                page = await browser.new_page(
                    user_agent=CREX_HEADERS["User-Agent"],
                    viewport={"width": 1365, "height": 900},
                )
                # CREX keeps analytics/live connections open, so network-idle
                # is not a reliable readiness signal for the rendered cards.
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                try:
                    await page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass
                await page.wait_for_timeout(1500)
                html = await page.content()
                anchors = await page.eval_on_selector_all(
                    "a",
                    """els => els.map(a => {
                        const href = a.href || a.getAttribute('href') || '';
                        const text = a.innerText || a.textContent || '';
                        return `<a href="${href.replaceAll('"', '&quot;')}">${text}</a>`;
                    }).join('\\n')""",
                )
                return f"{html}\n{anchors}"
            finally:
                await browser.close()
    except Exception as exc:
        logger.debug("Rendered CREX discovery failed for %s: %s", url, exc)
        return ""


def _browser_executable() -> str | None:
    """Find a local browser for rendered discovery without setup files."""
    configured = get_settings().PLAYWRIGHT_EXECUTABLE_PATH
    candidates = [configured] if configured else []
    candidates.extend([
        shutil.which("chrome"),
        shutil.which("msedge"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ])
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return None
