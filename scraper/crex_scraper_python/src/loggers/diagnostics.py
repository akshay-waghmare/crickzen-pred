"""Diagnostic artifact helpers for the cricket scraper."""

from __future__ import annotations

import json
import logging
import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

_LOGGER = logging.getLogger(__name__)

_ARTIFACT_ROOT_ENV = "SCRAPER_ARTIFACT_ROOT"
_ARTIFACT_RETENTION_ENV = "SCRAPER_ARTIFACT_RETENTION_DAYS"
_DEFAULT_RETENTION_DAYS = 14

_HTML_FILENAME = "page.html"
_SCREENSHOT_FILENAME = "page.png"
_STATE_FILENAME = "state.json"


def get_artifact_directory(
    subdirectory: str = "diagnostics",
    *,
    correlation_id: Optional[str] = None,
    create: bool = True,
) -> Path:
    """Return the directory that should hold diagnostics, creating it if needed."""

    base = _artifact_root(create=create)
    path = base

    if correlation_id:
        path = path / correlation_id

    if subdirectory:
        path = path / subdirectory

    if create:
        path.mkdir(parents=True, exist_ok=True)

    return path


def capture_html_snapshot(
    content: str,
    *,
    correlation_id: Optional[str] = None,
    filename: str = _HTML_FILENAME,
) -> Path:
    """Persist HTML content for later inspection and return the destination path."""

    directory = get_artifact_directory(subdirectory="", correlation_id=correlation_id)
    target = _unique_path(directory, filename)
    target.write_text(content, encoding="utf-8")
    return target


def capture_screenshot(
    image_bytes: bytes,
    *,
    correlation_id: Optional[str] = None,
    filename: str = _SCREENSHOT_FILENAME,
) -> Path:
    """Persist screenshot bytes aligned with the correlation scope."""

    directory = get_artifact_directory(subdirectory="", correlation_id=correlation_id)
    target = _unique_path(directory, filename)
    target.write_bytes(image_bytes)
    return target


def capture_state_dump(
    state: Any,
    *,
    correlation_id: Optional[str] = None,
    filename: str = _STATE_FILENAME,
) -> Path:
    """Persist serialized state for debugging and return the written path."""

    directory = get_artifact_directory(subdirectory="", correlation_id=correlation_id)
    target = _unique_path(directory, filename)
    serialised = json.dumps(state, default=_json_fallback, indent=2, sort_keys=True)
    target.write_text(serialised, encoding="utf-8")
    return target


def prune_expired_artifacts(max_age_seconds: Optional[int] = None) -> None:
    """Remove artifacts older than the configured retention window."""

    retention_seconds = _resolve_retention_seconds(max_age_seconds)

    if retention_seconds <= 0:
        return

    root = _artifact_root(create=False)

    if not root.exists():
        return

    cutoff = datetime.now(timezone.utc) - timedelta(seconds=retention_seconds)

    for entry in root.iterdir():
        if not entry.is_dir():
            continue

        try:
            mtime = datetime.fromtimestamp(entry.stat().st_mtime, tz=timezone.utc)
        except OSError as exc:
            _LOGGER.warning(
                "Failed to inspect artifact directory",
                extra={"path": str(entry), "error": str(exc)},
            )
            continue

        if mtime >= cutoff:
            continue

        try:
            shutil.rmtree(entry)
        except OSError as exc:
            _LOGGER.warning(
                "Failed to prune artifact directory",
                extra={"path": str(entry), "error": str(exc)},
            )


def _artifact_root(*, create: bool = True) -> Path:
    path = Path(os.getenv(_ARTIFACT_ROOT_ENV, "artifacts"))

    if create:
        path.mkdir(parents=True, exist_ok=True)

    return path


def _unique_path(directory: Path, filename: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    candidate = directory / filename

    if not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix
    counter = 1

    while candidate.exists():
        candidate = directory / f"{stem}_{counter}{suffix}"
        counter += 1

    return candidate


def _resolve_retention_seconds(max_age_seconds: Optional[int]) -> int:
    if max_age_seconds is not None:
        return max(0, int(max_age_seconds))

    env_value = os.getenv(_ARTIFACT_RETENTION_ENV)

    if env_value:
        try:
            days = int(env_value)
        except ValueError:
            days = _DEFAULT_RETENTION_DAYS
    else:
        days = _DEFAULT_RETENTION_DAYS

    return max(0, days * 24 * 60 * 60)


def _json_fallback(value: Any) -> str:
    return repr(value)
