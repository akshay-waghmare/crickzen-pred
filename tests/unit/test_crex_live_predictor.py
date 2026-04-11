import sys
from pathlib import Path

PROJECT_SRC = Path(__file__).resolve().parents[2] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from bbl_pipeline.inference.crex_live_predictor import CrexLivePredictor


def test_normalize_live_url_strips_info_suffixes():
    base_url = "https://crex.com/cricket-live-score/csk-vs-pbks-7th-match-indian-premier-league-2026-match-updates-10Y5"

    assert CrexLivePredictor._normalize_live_url(base_url + "/match-details") == base_url
    assert CrexLivePredictor._normalize_live_url(base_url + "/match-scorecard") == base_url
    assert CrexLivePredictor._normalize_live_url(base_url + "/scorecard") == base_url
    assert CrexLivePredictor._normalize_live_url(base_url) == base_url


def test_build_sidecar_paths_are_feed_specific():
    output_json = "data/ipl_live_ml.json"

    assert CrexLivePredictor._build_live_match_json_path(output_json) == "data\\ipl_live_ml_livematch.json"
    assert CrexLivePredictor._build_history_file_path(output_json) == "data\\ipl_live_ml_history.json"


def test_clean_team_text_removes_crex_section_labels():
    assert CrexLivePredictor._clean_team_text("PBKS in Points Table") == "PBKS"
    assert CrexLivePredictor._clean_team_text("Punjab Kings Team Form") == "Punjab Kings"


def test_resolve_team_name_uses_psl_abbreviations():
    predictor = CrexLivePredictor.__new__(CrexLivePredictor)
    predictor.local_storage = {}
    predictor.league = "psl"
    predictor.predictor = None

    assert predictor._resolve_team_name("ISU") == "Islamabad United"
    assert predictor._resolve_team_name("RWP") == "Rawalpindiz"
