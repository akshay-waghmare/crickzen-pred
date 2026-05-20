import os
import sys
from pathlib import Path


PROJECT_SRC = Path(__file__).resolve().parents[2] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from bbl_pipeline.app.live_source_defaults import CUSTOM_JSON_LABEL, select_initial_json_source


def test_select_initial_json_source_prefers_explicit_env_match(tmp_path):
    old_path = tmp_path / "ipl_live_ml_odm.json"
    new_path = tmp_path / "ipl_live_ml_1.json"
    old_path.write_text("{}", encoding="utf-8")
    new_path.write_text("{}", encoding="utf-8")

    sources = {
        "old": str(old_path),
        "new": str(new_path),
        "Custom path...": "__custom__",
    }

    label, custom_path = select_initial_json_source(
        sources,
        "data/live_state.json",
        env_json=str(new_path),
    )

    assert label == "new"
    assert custom_path is None


def test_select_initial_json_source_uses_freshest_existing_file_when_no_env(tmp_path):
    old_path = tmp_path / "ipl_live_ml_odm.json"
    new_path = tmp_path / "ipl_live_ml_1.json"
    old_path.write_text("{}", encoding="utf-8")
    new_path.write_text("{}", encoding="utf-8")

    older = 1_700_000_000
    newer = older + 60
    os.utime(old_path, (older, older))
    os.utime(new_path, (newer, newer))

    sources = {
        "old": str(old_path),
        "new": str(new_path),
        "Custom path...": "__custom__",
    }

    label, custom_path = select_initial_json_source(
        sources,
        "data/live_state.json",
        env_json="",
    )

    assert label == "new"
    assert custom_path is None


def test_select_initial_json_source_prefers_earlier_source_on_mtime_tie(tmp_path):
    first_path = tmp_path / "ipl_live_ml_odm_1.json"
    second_path = tmp_path / "ipl_live_ml_1.json"
    first_path.write_text("{}", encoding="utf-8")
    second_path.write_text("{}", encoding="utf-8")

    same = 1_700_000_120
    os.utime(first_path, (same, same))
    os.utime(second_path, (same, same))

    sources = {
        "mirror": str(first_path),
        "raw": str(second_path),
        "Custom path...": "__custom__",
    }

    label, custom_path = select_initial_json_source(
        sources,
        "data/live_state.json",
        env_json="",
    )

    assert label == "mirror"
    assert custom_path is None


def test_select_initial_json_source_falls_back_to_custom_for_unknown_env_path(tmp_path):
    known_path = tmp_path / "known.json"
    known_path.write_text("{}", encoding="utf-8")
    custom_path = tmp_path / "custom.json"

    sources = {
        "known": str(known_path),
        "Custom path...": "__custom__",
    }

    label, selected_path = select_initial_json_source(
        sources,
        "data/live_state.json",
        env_json=str(custom_path),
    )

    assert label == CUSTOM_JSON_LABEL
    assert selected_path == str(custom_path)
