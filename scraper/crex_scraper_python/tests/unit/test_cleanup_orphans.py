"""Unit tests for orphaned process cleanup."""

import pytest

from src.core.cleanup_orphans import (
    find_orphaned_chromium_processes,
    terminate_processes,
)


def test_find_orphaned_processes_returns_list():
    """find_orphaned_chromium_processes returns a list of PIDs."""
    pids = find_orphaned_chromium_processes()
    assert isinstance(pids, list)
    # Should be mostly empty on clean system
    assert len(pids) < 100


def test_terminate_processes_with_empty_list():
    """terminate_processes handles empty list gracefully."""
    count = terminate_processes([])
    assert count == 0


def test_terminate_processes_with_invalid_pid():
    """terminate_processes handles invalid PIDs gracefully."""
    # Use a PID that doesn't exist
    count = terminate_processes([999999])
    # Should not crash, may report 0 or 1 depending on error handling
    assert count >= 0
