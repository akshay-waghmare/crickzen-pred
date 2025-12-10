"""Minimal unit tests for diagnostic helpers."""

import json
from pathlib import Path

from src.logging.diagnostics import (
    capture_html_snapshot,
    capture_screenshot,
    capture_state_dump,
    get_artifact_directory,
    prune_expired_artifacts,
)


def test_artifact_directory_creation():
    """Verify artifact directory is created."""
    artifact_dir = get_artifact_directory(correlation_id="test-123")
    assert artifact_dir.exists()
    assert artifact_dir.is_dir()
    assert "test-123" in str(artifact_dir)


def test_html_snapshot_capture():
    """Verify HTML content can be captured."""
    html_content = "<html><body>Test</body></html>"
    path = capture_html_snapshot(html_content, correlation_id="test-html")
    
    assert path.exists()
    assert path.read_text(encoding="utf-8") == html_content


def test_screenshot_capture():
    """Verify screenshot bytes can be captured."""
    image_bytes = b"\x89PNG\r\n\x1a\n"
    path = capture_screenshot(image_bytes, correlation_id="test-screenshot")
    
    assert path.exists()
    assert path.read_bytes() == image_bytes


def test_state_dump_capture():
    """Verify state can be serialized and captured."""
    state = {"key": "value", "count": 42}
    path = capture_state_dump(state, correlation_id="test-state")
    
    assert path.exists()
    captured = json.loads(path.read_text(encoding="utf-8"))
    assert captured == state


def test_prune_expired_artifacts():
    """Verify pruning completes without error."""
    # Just verify it doesn't crash with minimal retention
    prune_expired_artifacts(max_age_seconds=0)
