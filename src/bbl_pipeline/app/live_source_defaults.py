"""Helpers for choosing the default live JSON source in Streamlit."""

from __future__ import annotations

from pathlib import Path


CUSTOM_JSON_LABEL = "Custom path..."


def _normalized_path(path_like: str | Path) -> str:
    return Path(path_like).as_posix().lower()


def select_initial_json_source(
    json_sources: dict[str, str],
    default_json: str,
    *,
    env_json: str | None = None,
) -> tuple[str, str | None]:
    """Return the best initial source label and optional custom path.

    Precedence:
    1. An explicit PREDICTOR_JSON value, if it matches a predefined source.
    2. The freshest existing predefined source by file mtime.
    3. The default JSON path, if it matches a predefined source.
    4. The first predefined source.
    5. Custom path, if the default path is only known as a custom value.
    """

    env_value = env_json
    if env_value:
        env_norm = _normalized_path(env_value)
        for label, path in json_sources.items():
            if path != "__custom__" and _normalized_path(path) == env_norm:
                return label, None
        return CUSTOM_JSON_LABEL, env_value

    candidates: list[tuple[float, int, str]] = []
    for order, (label, path) in enumerate(json_sources.items()):
        if path == "__custom__":
            continue
        candidate = Path(path)
        try:
            if not candidate.exists():
                continue
            candidates.append((candidate.stat().st_mtime, -order, label))
        except OSError:
            continue

    if candidates:
        _, _, label = max(candidates)
        return label, None

    default_norm = _normalized_path(default_json)
    for label, path in json_sources.items():
        if path != "__custom__" and _normalized_path(path) == default_norm:
            return label, None

    for label, path in json_sources.items():
        if path != "__custom__":
            return label, None

    return CUSTOM_JSON_LABEL, default_json
