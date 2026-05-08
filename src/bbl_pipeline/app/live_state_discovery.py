from __future__ import annotations

from datetime import datetime
from pathlib import Path

from bbl_pipeline.ops.prod_ops_agent import choose_active_state_json


AUTO_CURRENT_SOURCE_VALUE = "__auto_current__"


def discover_current_state_json(source_dir: Path, *, now: datetime | None = None) -> Path | None:
    """Return the best live-state JSON to display for the current match."""
    selected = choose_active_state_json(source_dir, now=now)
    if selected is not None:
        return selected

    candidates = [
        path
        for path in source_dir.glob("*.json")
        if not path.stem.endswith("_history") and not path.stem.endswith("_livematch")
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def resolve_live_state_path(
    selection: str | None,
    *,
    source_dir: Path,
    now: datetime | None = None,
) -> tuple[str | None, str | None]:
    """Resolve a UI source selection into a concrete live-state JSON path."""
    if selection != AUTO_CURRENT_SOURCE_VALUE:
        return selection, None

    discovered = discover_current_state_json(source_dir, now=now)
    if discovered is None:
        return None, f"No active dashboard state found in {source_dir}"

    return str(discovered), f"Auto-selected current feed: {discovered.name}"
