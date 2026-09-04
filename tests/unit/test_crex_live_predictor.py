import asyncio
import sys
from pathlib import Path
from datetime import datetime
import pytest
import pandas as pd

PROJECT_SRC = Path(__file__).resolve().parents[2] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from bbl_pipeline.inference.crex_live_predictor import CrexLivePredictor
from bbl_pipeline.inference.crex_live_predictor import MatchState as CrexMatchState
from bbl_pipeline.inference.predictor import Predictor
from bbl_pipeline.inference.schema import MatchState as PredictorMatchState
from bbl_pipeline.features.format_config import FormatConfig


class _ClosableBrowser:
    def __init__(self):
        self.closed = False

    async def close(self):
        self.closed = True


class _ClosablePlaywright:
    def __init__(self):
        self.stopped = False

    async def stop(self):
        self.stopped = True


class _MarketResponse:
    ok = True
    status = 200

    def __init__(self, payload):
        self.payload = payload

    async def json(self):
        return self.payload


class _MarketRequest:
    def __init__(self, payload):
        self.payload = payload
        self.urls = []

    async def get(self, url, **kwargs):
        self.urls.append(url)
        return _MarketResponse(self.payload)


class _MarketPage:
    def __init__(self, payload):
        self.request = _MarketRequest(payload)


def test_stop_closes_browser_and_playwright_driver():
    predictor = CrexLivePredictor.__new__(CrexLivePredictor)
    predictor._running = True
    browser = _ClosableBrowser()
    playwright = _ClosablePlaywright()
    predictor.browser = browser
    predictor._playwright = playwright

    asyncio.run(predictor.stop())

    assert predictor._running is False
    assert browser.closed is True
    assert playwright.stopped is True
    assert predictor.browser is None
    assert predictor._playwright is None


def test_normalize_live_url_strips_info_suffixes():
    base_url = "https://crex.com/cricket-live-score/csk-vs-pbks-7th-match-indian-premier-league-2026-match-updates-10Y5"

    assert CrexLivePredictor._normalize_live_url(base_url + "/match-details") == base_url
    assert CrexLivePredictor._normalize_live_url(base_url + "/match-scorecard") == base_url
    assert CrexLivePredictor._normalize_live_url(base_url + "/scorecard") == base_url
    assert CrexLivePredictor._normalize_live_url(base_url) == base_url


def test_extract_crex_api_key_from_match_url():
    url = (
        "https://crex.com/cricket-live-score/kas-vs-noi-eliminator-"
        "uttar-pradesh-t20-league-2026-match-updates-133R"
    )

    assert CrexLivePredictor._extract_crex_api_key(url) == "133R"
    assert CrexLivePredictor._extract_crex_api_key(url + "?key=11UK") == "11UK"


def test_process_api_data_records_crex_market_odds_without_instance_log():
    predictor = CrexLivePredictor.__new__(CrexLivePredictor)
    predictor.local_storage = {"t_SK_name": "Kashi Rudras"}
    predictor.match_state = CrexMatchState(
        batting_team="Kashi Rudras",
        bowling_team="Noida Kings",
    )
    predictor._last_market_update_at = None
    predictor._last_market_age_seconds = None

    predictor._process_api_data({"F": "^SK", "R": "48+5"})

    assert predictor.match_state.market_fav_team == "Kashi Rudras"
    assert predictor.match_state.market_back_odds == "48"
    assert predictor.match_state.market_lay_odds == "53"
    assert predictor.match_state.market_fav_prob == pytest.approx(100 / 148)
    assert predictor._last_market_update_at is not None


def test_poll_crex_market_odds_reads_direct_s_v3_payload():
    predictor = CrexLivePredictor.__new__(CrexLivePredictor)
    predictor.page = _MarketPage({"F": "^SK", "R": "48+5"})
    predictor.match_url = (
        "https://crex.com/cricket-live-score/kas-vs-noi-eliminator-"
        "uttar-pradesh-t20-league-2026-match-updates-133R"
    )
    predictor.original_match_url = predictor.match_url
    predictor.local_storage = {"t_SK_name": "Kashi Rudras"}
    predictor.match_state = CrexMatchState(
        batting_team="Kashi Rudras",
        bowling_team="Noida Kings",
    )
    predictor._last_market_api_fetch_at = None
    predictor._last_market_update_at = None
    predictor._last_market_age_seconds = None

    asyncio.run(predictor._poll_crex_market_odds())

    assert predictor.page.request.urls == ["https://api-v1.com/v10/sV3.php?key=133R"]
    assert predictor.match_state.market_fav_team == "Kashi Rudras"
    assert predictor.match_state.market_back_odds == "48"


def test_extract_authoritative_bowler_accepts_shared_bowler_data_shapes():
    payload = {
        "bowler_data": {
            "name": "K Siddhu",
            "score": "8",
            "ballsBowled": "6",
            "wicketsTaken": "0",
        }
    }

    assert CrexLivePredictor._extract_authoritative_bowler(payload) == {
        "name": "K Siddhu",
        "overs": 1.0,
        "runs": 8,
        "wickets": 0,
    }


def test_hydrate_current_bowler_from_shared_snapshot_populates_match_state():
    predictor = CrexLivePredictor.__new__(CrexLivePredictor)
    predictor.page = _MarketPage({
        "bowler_data": [{
            "name": "K Siddhu",
            "score": "8",
            "ballsBowled": "6",
            "wicketsTaken": "0",
        }]
    })
    predictor.match_url = (
        "https://crex.com/cricket-live-score/kas-vs-noi-eliminator-"
        "uttar-pradesh-t20-league-2026-match-updates-133R"
    )
    predictor.original_match_url = predictor.match_url
    predictor.match_state = CrexMatchState()
    predictor._last_bowler_api_fetch_at = None

    asyncio.run(predictor._hydrate_current_bowler_from_shared_snapshot())

    assert predictor.page.request.urls == [
        "https://www.crickzen.com/api/cricket-data/last-updated-data?url="
        "https%3A%2F%2Fcrex.com%2Fcricket-live-score%2Fkas-vs-noi-eliminator-"
        "uttar-pradesh-t20-league-2026-match-updates-133R"
    ]
    assert predictor.match_state.bowler1_name == "K Siddhu"
    assert predictor.match_state.bowler1_overs == pytest.approx(1.0)
    assert predictor.match_state.bowler1_runs == 8
    assert predictor.match_state.bowler_data_source == "crickzen_shared_live_snapshot"


def test_poll_and_predict_rehydrates_missing_bowler_before_prediction(monkeypatch):
    predictor = CrexLivePredictor.__new__(CrexLivePredictor)
    predictor.page = object()
    predictor._poll_count = 0
    predictor.model = None
    predictor.mc_only = True
    predictor._effective_total_overs = 20
    predictor.format_config = FormatConfig.t20()
    predictor.match_state = CrexMatchState(
        batting_team="St Lucia Kings",
        bowling_team="St Kitts & Nevis Patriots",
    )
    predictor._team1_name_hint = "St Kitts & Nevis Patriots"
    predictor._team2_name_hint = "St Lucia Kings"
    hydrate_calls = []

    async def no_op_market_poll():
        return None

    async def no_op_dom_extract():
        return None

    async def hydrate(*, force=False):
        hydrate_calls.append(force)
        predictor.match_state.bowler1_name = "J Louis"
        predictor.match_state.bowler1_overs = 1.0
        predictor.match_state.bowler1_runs = 4
        predictor.match_state.bowler1_wickets = 1
        predictor.match_state.bowler_data_source = "crickzen_shared_live_snapshot"

    monkeypatch.setattr(predictor, "_poll_crex_market_odds", no_op_market_poll)
    monkeypatch.setattr(predictor, "_extract_match_info", no_op_dom_extract)
    monkeypatch.setattr(predictor, "_hydrate_current_bowler_from_shared_snapshot", hydrate)
    monkeypatch.setattr(predictor, "_run_prediction", lambda: 0.5)

    assert asyncio.run(predictor.poll_and_predict()) == 0.5
    assert hydrate_calls == [True]
    assert predictor.match_state.bowler1_name == "J Louis"
    assert predictor.match_state.bowler_data_source == "crickzen_shared_live_snapshot"


def test_shared_snapshot_batting_team_forces_authoritative_opposing_team():
    predictor = CrexLivePredictor.__new__(CrexLivePredictor)
    predictor.local_storage = {}
    predictor.league = "t20_all"
    predictor.predictor = None
    predictor._team1_name_hint = "St Kitts & Nevis Patriots"
    predictor._team2_name_hint = "St Lucia Kings"
    predictor.match_url = (
        "https://crex.com/cricket-live-score/sknp-vs-slk-25th-match-"
        "caribbean-premier-league-2026-match-updates-11UK"
    )
    predictor.original_match_url = predictor.match_url
    predictor.match_state = CrexMatchState(
        batting_team="St Lucia Kings",
        bowling_team="A Nedd",
    )

    predictor._apply_authoritative_snapshot_teams({"batting_team": "SLK"})

    assert predictor.match_state.batting_team == "St Lucia Kings"
    assert predictor.match_state.bowling_team == "St Kitts & Nevis Patriots"


def test_repair_match_teams_does_not_preserve_player_as_opposing_team():
    predictor = CrexLivePredictor.__new__(CrexLivePredictor)
    predictor.local_storage = {}
    predictor.league = "t20_all"
    predictor.predictor = None
    predictor._team1_name_hint = "St Kitts & Nevis Patriots"
    predictor._team2_name_hint = "St Lucia Kings"
    predictor.match_url = (
        "https://crex.com/cricket-live-score/sknp-vs-slk-25th-match-"
        "caribbean-premier-league-2026-match-updates-11UK"
    )
    predictor.original_match_url = predictor.match_url
    predictor.match_state = CrexMatchState(
        batting_team="St Lucia Kings",
        bowling_team="A Nedd",
    )

    predictor._repair_match_teams_from_url()

    assert predictor.match_state.batting_team == "St Lucia Kings"
    assert predictor.match_state.bowling_team == "St Kitts & Nevis Patriots"


def test_build_sidecar_paths_are_feed_specific():
    output_json = "data/ipl_live_ml.json"

    assert CrexLivePredictor._build_live_match_json_path(output_json) == "data\\ipl_live_ml_livematch.json"
    assert CrexLivePredictor._build_history_file_path(output_json) == "data\\ipl_live_ml_history.json"


def test_clean_team_text_removes_crex_section_labels():
    assert CrexLivePredictor._clean_team_text("PBKS in Points Table") == "PBKS"
    assert CrexLivePredictor._clean_team_text("Punjab Kings Team Form") == "Punjab Kings"


def test_extract_score_snapshot_from_current_crex_title():
    title = (
        "PD 74-2 (6.0) (Dev Lakra 2(4), Aryan Gaur 33(16)) vs "
        "East Delhi Riders 118-6 ((10.0)) 40th-Match | Delhi Premier T20 League 2026 - CREX"
    )

    assert CrexLivePredictor._extract_score_snapshot(title) == ("PD", 74, 2, 6.0)


def test_extract_score_snapshot_falls_back_to_hydrated_score_rows():
    body = """
    Match Details
    PD
    71-2
    5.3
    1
    CRR : 12.91
    RRR : 10.67
    PD need 48 runs in 27 balls
    Commentary
    Purani Dilli-6
    69/2
    """

    assert CrexLivePredictor._extract_score_snapshot(body, preferred_team="PD") == (
        "PD",
        71,
        2,
        5.3,
    )


def test_capture_first_innings_summary_accepts_current_crex_slash_format():
    predictor = CrexLivePredictor.__new__(CrexLivePredictor)
    predictor.match_state = CrexMatchState(target=234, is_second_innings=True)
    predictor._inn1_page_stats = {}

    predictor._capture_first_innings_summary(
        'India 233/10(44.0) England 96/4 (19.3)'
    )

    assert predictor._inn1_page_stats == {
        "inn1_wickets_lost": 10,
        "inn1_summary_score": 233,
        "inn1_summary_overs": 44.0,
        "inn1_stats_source": "crex_summary",
    }


def test_capture_first_innings_summary_rejects_score_not_matching_target():
    predictor = CrexLivePredictor.__new__(CrexLivePredictor)
    predictor.match_state = CrexMatchState(target=240, is_second_innings=True)
    predictor._inn1_page_stats = {}

    predictor._capture_first_innings_summary('India 233/10 (44.0) England 96/4 (19.3)')

    assert predictor._inn1_page_stats == {}


class _CapturingOdmModel:
    def __init__(self):
        self.current_ml_prob = None

    def predict(self, **kwargs):
        self.current_ml_prob = kwargs["current_ml_prob"]
        return {"status": "ready"}


class _FeatureMapperStub:
    def create_feature_dataframe(self, scraped_data):
        return pd.DataFrame(
            [
                {
                    "innings": scraped_data["innings_num"],
                    "over": scraped_data["over_number"],
                    "wickets_lost": scraped_data["total_wickets"],
                    "overs_remaining": 20 - scraped_data["over_number"] - scraped_data["ball_number"] / 6,
                    "current_run_rate": 9.0,
                    "required_run_rate": 8.0,
                    "run_rate_diff": 1.0,
                    "score_vs_par": 8.0,
                    "target_above_par": 5.0,
                    "resource_win_prob": 0.55,
                    "resource_pct": 0.45,
                    "resources_remaining": 0.5,
                    "pressure_index": 9.2,
                    "dls_pressure_index": 0.42,
                    "runs_last_12": 22,
                    "runs_last_18": 32,
                    "wickets_last_12": 0,
                    "wickets_last_6": 0,
                    "dot_pct_last_12": 0.25,
                    "boundary_pct_last_18": 0.22,
                    "balls_since_wicket": 31,
                    "set_batter_exposure": max(
                        scraped_data["batsman1_balls"],
                        scraped_data["batsman2_balls"],
                    ),
                    "batting_pair_strength": 54.0,
                    "team_strength_diff": 0.0,
                    "crr_times_res": 4.5,
                    "acceleration_potential": 10.0,
                    "inn1_defendability": 0.5,
                    "inn1_pp_runs": 50.0,
                    "inn1_death_rr": 10.0,
                    "inn1_wickets_lost": 7.0,
                }
            ]
        )


class _PredictorStub:
    feature_mapper = _FeatureMapperStub()


def test_update_odm_prediction_uses_displayed_probability_when_provided():
    predictor = CrexLivePredictor.__new__(CrexLivePredictor)
    predictor.odm_model_dir = "models/odm_v1"
    predictor.predictor = object()
    predictor.odm_model = _CapturingOdmModel()
    predictor.match_state = CrexMatchState(
        batting_team="Gujarat Titans",
        bowling_team="Kolkata Knight Riders",
        target=200,
        is_second_innings=True,
        venue="Eden Gardens",
    )
    predictor.league = "ipl"
    predictor._prediction_history = [{"innings": 2, "over": 1, "ball": 1, "bat_prob": 0.31}]
    predictor.last_raw_prob = 0.72

    predictor._update_odm_prediction({"resource_win_prob": 0.4}, 8, 3, current_ml_prob=0.33)

    assert predictor.odm_model.current_ml_prob == 0.33
    assert predictor.last_odm_prediction == {"status": "ready"}


def test_live_feature_snapshot_exports_engineered_partnership_features():
    predictor = CrexLivePredictor.__new__(CrexLivePredictor)
    predictor.predictor = _PredictorStub()
    predictor.match_state = CrexMatchState(
        batting_team="Sunrisers Hyderabad",
        bowling_team="Chennai Super Kings",
        total_runs=113,
        wickets=2,
        overs=12.5,
        target=181,
        is_second_innings=True,
        batsman1_name="Ishan Kishan",
        batsman1_balls=30,
        batsman2_name="Heinrich Klaasen",
        batsman2_balls=20,
        venue="MA Chidambaram Stadium, Chennai",
    )
    predictor._get_carryover_scraped_fields = lambda: {"first_innings_score": 180}

    _, _, features = predictor._build_live_feature_snapshot()

    assert features["set_batter_exposure"] == 30.0
    assert features["wicket_free_balls"] == 31.0
    assert features["partnership_solidity"] > 0.7


def test_resolve_team_name_uses_psl_abbreviations():
    predictor = CrexLivePredictor.__new__(CrexLivePredictor)
    predictor.local_storage = {}
    predictor.league = "psl"
    predictor.predictor = None

    assert predictor._resolve_team_name("ISU") == "Islamabad United"
    assert predictor._resolve_team_name("RWP") == "Rawalpindiz"


def test_extract_vs_teams_stops_before_preview_sentence():
    predictor = CrexLivePredictor.__new__(CrexLivePredictor)
    predictor.local_storage = {}
    predictor.league = "ipl"
    predictor.predictor = None

    teams = predictor._extract_vs_teams(
        "CSK vs MI neither Rohit nor MS Dhoni is part of an MI vs CSK game"
    )

    assert teams == ("Chennai Super Kings", "Mumbai Indians")


def test_extract_teams_from_crex_url_prefers_ipl_codes():
    predictor = CrexLivePredictor.__new__(CrexLivePredictor)
    predictor.local_storage = {}
    predictor.league = "ipl"
    predictor.predictor = None
    predictor.match_url = (
        "https://crex.com/cricket-live-score/csk-vs-mi-33rd-match-"
        "indian-premier-league-2026-match-updates-118E"
    )
    predictor.original_match_url = predictor.match_url

    assert predictor._extract_teams_from_url() == ("Chennai Super Kings", "Mumbai Indians")


def test_extract_teams_from_crex_url_prefers_provider_authoritative_names():
    predictor = CrexLivePredictor.__new__(CrexLivePredictor)
    predictor.local_storage = {}
    predictor.league = "t20_all"
    predictor.predictor = None
    predictor._team1_name_hint = "Dublin Guardians"
    predictor._team2_name_hint = "Rotterdam Dockers"
    predictor.match_url = (
        "https://crex.com/cricket-live-score/dg-vs-rd-10th-match-"
        "european-t20-premier-league-2026-match-updates-13F3"
    )
    predictor.original_match_url = predictor.match_url

    assert predictor._extract_teams_from_url() == ("Dublin Guardians", "Rotterdam Dockers")


def test_scorecard_team_label_uses_provider_pair_for_batting_orientation():
    predictor = CrexLivePredictor.__new__(CrexLivePredictor)
    predictor.local_storage = {"t_RD_name": "Dhaka Gladiators"}
    predictor.league = "t20_all"
    predictor.predictor = None
    predictor._team1_name_hint = "Dublin Guardians"
    predictor._team2_name_hint = "Rotterdam Dockers"
    predictor.match_url = (
        "https://crex.com/cricket-live-score/dg-vs-rd-10th-match-"
        "european-t20-premier-league-2026-match-updates-13F3"
    )
    predictor.original_match_url = predictor.match_url

    assert predictor._resolve_scorecard_team_from_provider_pair("RD") == "Rotterdam Dockers"
    assert predictor._resolve_scorecard_team_from_provider_pair("DG") == "Dublin Guardians"


def test_first_innings_summary_does_not_flip_current_innings_for_same_team():
    assert not CrexLivePredictor._second_innings_is_supported(
        current_team="Jalandhar Warriors",
        current_runs=205,
        first_innings_team="Jalandhar Warriors",
        first_innings_runs=205,
    )


def test_first_innings_summary_supports_chase_for_other_team():
    assert CrexLivePredictor._second_innings_is_supported(
        current_team="Bathinda Royals",
        current_runs=10,
        first_innings_team="Jalandhar Warriors",
        first_innings_runs=205,
    )


def test_explicit_chase_text_is_authoritative_even_without_team_resolution():
    assert CrexLivePredictor._second_innings_is_supported(
        current_team="Unknown",
        current_runs=0,
        first_innings_team="",
        first_innings_runs=-1,
        has_needs_runs=True,
    )


def test_rejects_first_innings_summary_as_current_bowler():
    assert not CrexLivePredictor._current_bowler_is_valid(
        "st innings over", 205, 10, 19.3
    )
    assert CrexLivePredictor._current_bowler_is_valid("S Sharma", 0, 39, 3.2)


def test_extract_teams_from_crex_url_resolves_women_t20i_suffixes():
    predictor = CrexLivePredictor.__new__(CrexLivePredictor)
    predictor.local_storage = {}
    predictor.league = "t20i_female"
    predictor.predictor = None
    predictor.match_url = (
        "https://crex.com/cricket-live-score/ind-w-vs-sa-w-5th-t20-"
        "india-women-tour-of-south-africa-2026-match-updates-ZGA"
    )
    predictor.original_match_url = predictor.match_url

    assert predictor._resolve_team_name("IND-W") == "India"
    assert predictor._resolve_team_name("SA-W") == "South Africa"
    assert predictor._extract_teams_from_url() == ("India", "South Africa")


def test_extract_batter_pair_accepts_initials_stars_and_hyphens():
    pair = CrexLivePredictor._extract_batter_pair(
        "CSK 126-2 (14.5) (S Dube 43*(24), R Jadeja-Singh 6(2))"
    )

    assert pair == ("S Dube", 43, 24, "R Jadeja-Singh", 6, 2)


def test_repair_match_teams_replaces_article_snippet():
    predictor = CrexLivePredictor.__new__(CrexLivePredictor)
    predictor.local_storage = {}
    predictor.league = "ipl"
    predictor.predictor = None
    predictor.match_url = (
        "https://crex.com/cricket-live-score/csk-vs-mi-33rd-match-"
        "indian-premier-league-2026-match-updates-118E"
    )
    predictor.original_match_url = predictor.match_url
    predictor.match_state = type("State", (), {})()
    predictor.match_state.batting_team = "Chennai Super Kings"
    predictor.match_state.bowling_team = "neither Rohit nor MS Dhoni is part of an MI"

    predictor._repair_match_teams_from_url()

    assert predictor.match_state.bowling_team == "Mumbai Indians"


def test_repair_match_teams_replaces_a_valid_but_unrelated_page_snippet():
    predictor = CrexLivePredictor.__new__(CrexLivePredictor)
    predictor.local_storage = {}
    predictor.league = "t20_all"
    predictor.predictor = None
    predictor.match_url = (
        "https://crex.com/cricket-live-score/ck-vs-jk-12th-match-lanka-"
        "premier-league-2026-match-updates-TEST"
    )
    predictor.original_match_url = predictor.match_url
    predictor.match_state = type("State", (), {})()
    predictor.match_state.batting_team = "Canterbury"
    predictor.match_state.bowling_team = "Jammu & Kashmir"

    predictor._repair_match_teams_from_url()

    assert predictor.match_state.batting_team == "Colombo Kaps"
    assert predictor.match_state.bowling_team == "Jaffna Kings"


def test_repair_match_teams_preserves_nep_a_live_batting_identity():
    predictor = CrexLivePredictor.__new__(CrexLivePredictor)
    predictor.local_storage = {}
    predictor.league = "t20_all"
    predictor.predictor = None
    predictor.match_url = (
        "https://crex.com/cricket-live-score/hyk-vs-nep-a-20th-match-top-end-"
        "t20-series-2026-match-updates-13KJ"
    )
    predictor.original_match_url = predictor.match_url
    predictor.match_state = type("State", (), {})()
    predictor.match_state.batting_team = "NEP-A"
    predictor.match_state.bowling_team = "Hyderabad Kingsmen Academy"

    assert predictor._extract_teams_from_url() == ("HYK", "NEP-A")

    predictor._repair_match_teams_from_url()

    assert predictor.match_state.batting_team == "NEP-A"
    assert predictor.match_state.bowling_team == "Hyderabad Kingsmen Academy"


def test_clean_venue_text_removes_broadcast_tail():
    assert (
        CrexLivePredictor._clean_venue_text(
            "Wankhede Stadium, Mumbai Star Sports Network, JioHotstar MI"
        )
        == "Wankhede Stadium, Mumbai"
    )


def test_predictor_terminal_clamp_handles_innings_2_all_out():
    predictor = Predictor.__new__(Predictor)
    predictor.format_config = FormatConfig.t20()

    state = PredictorMatchState(
        match_id="test",
        venue="Wankhede Stadium",
        batting_team="Chennai Super Kings",
        bowling_team="Mumbai Indians",
        innings=2,
        over=18,
        ball=0,
        current_score=170,
        wickets_lost=10,
        batsman_1="Unknown",
        batsman_2="Unknown",
        bowler="Unknown",
        target_runs=210,
    )

    clamp = predictor._second_innings_terminal_clamp(state)

    assert clamp["applied"] is True
    assert clamp["reason"] == "all_out"
    assert clamp["probability"] == 0.0


class _FixedStackModel:
    def predict_proba(self, X):
        import numpy as np

        return np.array([[0.2, 0.8]])


def test_market_stack_overlay_is_dry_run_and_uses_innings_1_space():
    predictor = CrexLivePredictor.__new__(CrexLivePredictor)
    predictor.market_stack = {
        "model": _FixedStackModel(),
        "input_features": ["logit_iso_p_inn1", "logit_market_p_inn1"],
        "probability_space": "p_innings1_wins",
        "applies_to": "innings_2_only",
    }
    predictor.market_stack_model_dir = "models\\ipl_v7_inn2_market_stack_candidate"
    predictor._last_market_update_at = datetime.now()
    predictor._last_terminal_clamp = None
    predictor.match_state = type("State", (), {"is_second_innings": True})()

    result = predictor._compute_market_stack_overlay(
        win_prob=0.30,
        market_batting_prob=0.10,
    )

    assert result["status"] == "ready"
    assert result["used_for_primary"] is False
    assert result["is_dry_run"] is True
    assert result["base_inn1_win_prob"] == pytest.approx(0.70)
    assert result["market_inn1_win_prob"] == pytest.approx(0.90)
    assert result["stack_inn1_win_prob"] == pytest.approx(0.80)
    assert result["stack_bat_win_prob"] == pytest.approx(0.20)
