import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.launcher import (
    build_slot_display_json,
    build_slot_output_json,
    format_output_json_hint,
    format_slot_output_hint,
)


def test_build_slot_output_json_uses_slot_suffix():
    assert build_slot_output_json("data/ipl_live_ml.json", 0) == str(Path("data/ipl_live_ml_1.json"))
    assert build_slot_output_json("data/psl_live_ml.json", 2) == str(Path("data/psl_live_ml_3.json"))


def test_build_slot_display_json_uses_odm_mirror_for_ipl_and_psl():
    assert build_slot_display_json(
        "data/ipl_live_ml.json",
        0,
        display_json="data/ipl_live_ml_odm.json",
    ) == str(Path("data/ipl_live_ml_odm_1.json"))
    assert build_slot_display_json(
        "data/psl_live_ml.json",
        1,
        display_json="data/psl_live_ml_odm.json",
    ) == str(Path("data/psl_live_ml_odm_2.json"))


def test_build_slot_display_json_falls_back_to_mc_output_for_mc_only():
    assert build_slot_display_json(
        "data/ipl_live_ml.json",
        0,
        mc_only=True,
        display_json="data/ipl_live_ml_odm.json",
    ) == str(Path("data/ipl_live_mc_1.json"))


def test_format_output_json_hint_uses_windows_style_path():
    assert format_output_json_hint("data/ipl_live_ml_1.json") == "Output JSON: data\\ipl_live_ml_1.json"


def test_format_slot_output_hint_includes_odm_mirror_when_present():
    hint = format_slot_output_hint("data/ipl_live_ml_1.json", "data/ipl_live_ml_odm_1.json")
    assert "ipl_live_ml_1.json" in hint
    assert "ipl_live_ml_odm_1.json" in hint
