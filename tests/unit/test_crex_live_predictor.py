import json
import sys
from pathlib import Path

PROJECT_SRC = Path(__file__).resolve().parents[2] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from bbl_pipeline.features.format_config import FormatConfig
from bbl_pipeline.inference.predictor import DummyFeatureStore
from bbl_pipeline.inference.crex_live_predictor import CrexLivePredictor, MatchState


def _make_stub_predictor():
    predictor = CrexLivePredictor.__new__(CrexLivePredictor)
    predictor.local_storage = {}
    predictor.league = "ipl"
    predictor.predictor = None
    predictor.model = None
    predictor.match_state = MatchState()
    predictor.match_state_logger = None
    predictor._prediction_history = []
    predictor._history_file = None
    predictor.output_json = None
    predictor.live_match_json = None
    predictor.feature_store_dir = None
    predictor.model_dir = "models/t20_male_v2"
    predictor._effective_total_overs = None
    predictor.format_config = FormatConfig.t20()
    predictor.mc_only = False
    predictor.match_url = "https://crex.com/cricket-live-score/example"
    predictor.use_ml_model = False
    predictor._cli_revised_target = None
    predictor.last_ball_number = ""
    predictor.match_status = "scheduled"
    predictor.match_status_reason = "Waiting for live score from CREX"
    predictor.prediction_status_reason = "Waiting for live score from CREX"
    predictor._latest_page_title = ""
    predictor._latest_page_text = ""
    predictor._save_history = lambda: None
    return predictor


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
    assert CrexLivePredictor._clean_team_text("DC Head to Head") == "DC"


def test_extract_vs_teams_ignores_head_to_head_suffix():
    predictor = CrexLivePredictor.__new__(CrexLivePredictor)
    predictor.local_storage = {}
    predictor.league = "ipl"
    predictor.predictor = None

    assert predictor._extract_vs_teams("DC vs RR Head to Head") == (
        "Delhi Capitals",
        "Rajasthan Royals",
    )


def test_extract_live_score_from_page_text_reads_top_score_block():
    predictor = CrexLivePredictor.__new__(CrexLivePredictor)
    predictor.local_storage = {}
    predictor.league = "ipl"
    predictor.predictor = None

    page_text = (
        "Match Details\n"
        "# DC vs RR, 43rd T20, IPL 2026 live\n"
        "RR\n"
        "PP\n"
        "17-2 2.5\n"
        "0\n"
        "CRR : 6.00\n"
        "RR opt to Bat\n"
    )

    assert predictor._extract_live_score_from_page_text(page_text) == ("Rajasthan Royals", 17, 2, 2.5)


def test_detect_match_status_treats_zero_zero_title_as_live():
    predictor = _make_stub_predictor()

    status, reason = predictor._detect_match_status(
        "Delhi Capitals 0-0 (0.0) vs Chennai Super Kings | CREX",
        "Live commentary starts soon",
    )

    assert status == "live"
    assert "Live score" in reason


def test_detect_match_status_uses_toss_when_score_not_started():
    predictor = _make_stub_predictor()
    predictor.match_state.toss_winner = "DC"

    status, reason = predictor._detect_match_status(
        "DC vs CSK | CREX",
        "Delhi Capitals won the toss and opt to bat",
    )

    assert status == "toss"
    assert "Toss complete" in reason


def test_detect_match_status_ignores_batting_commentary_delayed_word():
    predictor = _make_stub_predictor()

    status, reason = predictor._detect_match_status(
        "Sunrisers Hyderabad 32-0 (2.2) vs Punjab Kings | CREX",
        "PUMMELLED! MAXIMUM! The batter delayed his bat swing and launched it straight down the ground.",
    )

    assert status == "live"
    assert "Live score" in reason


def test_detect_match_status_marks_completed_first_innings_as_break():
    predictor = _make_stub_predictor()
    predictor.match_state.overs = 20.0
    predictor.match_state.wickets = 6

    status, reason = predictor._detect_match_status(
        "Delhi Capitals 180-6 (20.0) vs Chennai Super Kings | CREX",
        "End of innings",
    )

    assert status == "innings_break"
    assert "next innings" in reason


def test_can_predict_current_state_blocks_interruption():
    predictor = _make_stub_predictor()
    predictor.match_status = "interrupted"
    predictor.match_status_reason = "Play interrupted after live scoring started"
    predictor.match_state.batting_team = "Delhi Capitals"
    predictor.match_state.bowling_team = "Chennai Super Kings"

    can_predict, reason = predictor._can_predict_current_state()

    assert can_predict is False
    assert "interrupted" in reason.lower()


def test_display_state_writes_json_even_without_prediction(tmp_path):
    predictor = _make_stub_predictor()
    predictor.output_json = str(tmp_path / "live_state.json")
    predictor.match_state.batting_team = "Delhi Capitals"
    predictor.match_state.bowling_team = "Chennai Super Kings"
    predictor.match_status = "toss"
    predictor.match_status_reason = "Toss complete; waiting for the first ball"
    predictor.prediction_status_reason = "Toss complete; waiting for the first ball"

    calls = []
    predictor._write_json_state = lambda win_prob: calls.append(win_prob)

    predictor._display_state(None)

    assert calls == [None]


def test_write_json_state_marks_prediction_unavailable(tmp_path):
    predictor = _make_stub_predictor()
    output_path = tmp_path / "live_state.json"
    predictor.output_json = str(output_path)
    predictor.match_state = MatchState(
        batting_team="Delhi Capitals",
        bowling_team="Chennai Super Kings",
        total_runs=0,
        wickets=0,
        overs=0.0,
    )
    predictor.match_status = "toss"
    predictor.match_status_reason = "Toss complete; waiting for the first ball"
    predictor.prediction_status_reason = "Toss complete; waiting for the first ball"

    predictor._write_json_state(None)

    data = json.loads(output_path.read_text())
    assert data["match_status"] == "toss"
    assert data["prediction_available"] is False
    assert data["prediction_status_reason"] == "Toss complete; waiting for the first ball"
    assert data["bat_win_prob"] is None
    assert data["bowl_win_prob"] is None


def test_dummy_feature_store_provides_safe_live_fallbacks():
    store = DummyFeatureStore()

    assert store.get_team_stats("Delhi Capitals")["win_rate"] == 0.5
    assert store.get_venue_stats("Arun Jaitley Stadium")["venue_avg_score"] == 160.0
    assert store.get_venue_over_par("Arun Jaitley Stadium", 10) == 80.0
    assert store.get_player_venue_batting_stats("KL Rahul", "Arun Jaitley Stadium") == {}
