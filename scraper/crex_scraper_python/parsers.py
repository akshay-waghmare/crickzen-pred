"""DOM selector utilities with fallback resolution for the scraper service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, List, Mapping, Optional, Sequence

try:  # pragma: no cover - type checking only
    from typing import TYPE_CHECKING

    if TYPE_CHECKING:  # pragma: no cover
        from playwright.sync_api import ElementHandle
except ImportError:  # pragma: no cover - typing fallback when playwright missing
    TYPE_CHECKING = False  # type: ignore[misc]

from src.logging.adapters import get_logger

logger = get_logger(component="parsers")


SELECTORS: Mapping[str, Sequence[str]] = {
    # Elements containing the "LIVE" chip within match listing cards
    "live_match_badge": (
        "div.live-card .live",
        "[data-testid='live-card'] .live",
        ".live-match-card .live",
        "[data-status='live']",
    ),
    # Anchors that follow the badge and lead to the match details page
    "live_match_anchor": (
        ":scope >> xpath=../following-sibling::*[1]",
        ":scope >> xpath=../../following-sibling::*[1]",
        ":scope >> xpath=ancestor::div[contains(@class,'live-card')][1]//a[contains(@href,'match')]",
        ":scope >> xpath=ancestor::a[1]",
        "a[href*='/match/']",
    ),
}


@dataclass
class SelectorResolutionError(RuntimeError):
    """Raised when no selector in the fallback chain resolves to a node."""

    selector_key: str
    selectors: Sequence[str]
    context: Optional[Mapping[str, Any]] = None
    message: Optional[str] = None

    def __post_init__(self) -> None:  # pragma: no cover - simple formatting
        details = {
            "selector_key": self.selector_key,
            "attempted_selectors": list(self.selectors),
        }
        if self.context:
            details.update(self.context)
        base = self.message or "All selectors failed to resolve"
        super().__init__(f"{base}: {details}")


def _log_fallback_hit(
    selector_key: str,
    selector: str,
    attempt_index: int,
    total_attempts: int,
    metadata: Optional[Mapping[str, Any]],
) -> None:
    level = "selector.fallback.hit" if attempt_index > 0 else "selector.primary.hit"
    logger.info(
        level,
        metadata={
            "selector_key": selector_key,
            "selector": selector,
            "attempt": attempt_index + 1,
            "attempts_total": total_attempts,
            **(metadata or {}),
        },
    )


def _log_selector_failure(
    selector_key: str,
    selectors: Sequence[str],
    metadata: Optional[Mapping[str, Any]],
    exc: Optional[Exception],
) -> None:
    log_metadata = {
        "selector_key": selector_key,
        "attempted_selectors": list(selectors),
        **(metadata or {}),
    }
    if exc is not None:
        log_metadata["error"] = str(exc)
        log_metadata["error_type"] = type(exc).__name__
    logger.error("selector.all_failed", metadata=log_metadata)


def select_first(
    handle: Any,
    selector_key: str,
    *,
    log_context: Optional[Mapping[str, Any]] = None,
    required: bool = False,
) -> Optional[Any]:
    """Return the first element resolved for ``selector_key`` using fallbacks."""

    selectors = SELECTORS.get(selector_key)
    if not selectors:
        raise KeyError(f"Unknown selector key: {selector_key}")

    last_exception: Optional[Exception] = None

    for attempt_index, selector in enumerate(selectors):
        try:
            result = handle.query_selector(selector)
        except Exception as exc:  # pragma: no cover - defensive logging
            last_exception = exc
            logger.warning(
                "selector.query_error",
                metadata={
                    "selector_key": selector_key,
                    "selector": selector,
                    "attempt": attempt_index + 1,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                    **(log_context or {}),
                },
            )
            continue

        if result:
            _log_fallback_hit(selector_key, selector, attempt_index, len(selectors), log_context)
            return result

    if required:
        _log_selector_failure(selector_key, selectors, log_context, last_exception)
        raise SelectorResolutionError(selector_key, selectors, log_context)

    return None


def select_all(
    handle: Any,
    selector_key: str,
    *,
    log_context: Optional[Mapping[str, Any]] = None,
    required: bool = False,
) -> List[Any]:
    """Return all elements resolved for ``selector_key`` using fallbacks."""

    selectors = SELECTORS.get(selector_key)
    if not selectors:
        raise KeyError(f"Unknown selector key: {selector_key}")

    last_exception: Optional[Exception] = None

    for attempt_index, selector in enumerate(selectors):
        try:
            results = handle.query_selector_all(selector)
        except Exception as exc:  # pragma: no cover - defensive logging
            last_exception = exc
            logger.warning(
                "selector.query_error",
                metadata={
                    "selector_key": selector_key,
                    "selector": selector,
                    "attempt": attempt_index + 1,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                    **(log_context or {}),
                },
            )
            continue

        if results:
            _log_fallback_hit(selector_key, selector, attempt_index, len(selectors), log_context)
            return list(results)

    if required:
        _log_selector_failure(selector_key, selectors, log_context, last_exception)
        raise SelectorResolutionError(selector_key, selectors, log_context)

    return []


def extract_match_href(
    handle: Any,
    *,
    log_context: Optional[Mapping[str, Any]] = None,
) -> str:
    """Resolve the match hyperlink associated with a live match badge."""

    anchor = select_first(handle, "live_match_anchor", log_context=log_context, required=True)
    if anchor is None:
        raise SelectorResolutionError("live_match_anchor", SELECTORS["live_match_anchor"], log_context)

    href = anchor.get_attribute("href")
    if href:
        return href

    logger.error(
        "selector.anchor_missing_href",
        metadata={
            "selector_key": "live_match_anchor",
            **(log_context or {}),
        },
    )
    raise SelectorResolutionError(
        "live_match_anchor",
        SELECTORS["live_match_anchor"],
        log_context,
        message="Resolved anchor missing href",
    )


__all__ = [
    "SELECTORS",
    "SelectorResolutionError",
    "select_first",
    "select_all",
    "extract_match_href",
]
