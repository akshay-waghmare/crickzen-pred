import asyncio

from app.auto_scheduler import AutoPredictionScheduler, MatchCandidate, SYSTEM_USER_ID, extract_crex_match_candidates
from app.auto_scheduler import _browser_executable, _looks_live
from app.config import Settings
from app.prediction_manager import PredictionManager


def test_all_mode_keeps_format_leagues_and_applies_exclusions():
    settings = Settings(
        AUTO_LEAGUE_KEYS="ALL",
        AUTO_EXCLUDE_LEAGUES="IPL",
    )
    scheduler = AutoPredictionScheduler(PredictionManager.get_instance(), settings)

    leagues = scheduler._target_leagues()

    assert "IPL" not in leagues
    assert "ODI Women" in leagues
    assert "ODI Male" in leagues
    assert "Women T20I" in leagues
    assert "NTB" in leagues


def test_discovery_classifies_full_urls_without_a_manual_match_list():
    html = """
    <a href="/cricket-live-score/ire-w-vs-wi-w-2nd-odi-west-indies-women-tour-of-ireland-2026-match-updates-114T">
      Ireland Women vs West Indies Women
    </a>
    <a href="/cricket-live-score/ess-vs-sur-107th-match-t20-blast-2026-match-updates-ZXR">
      Essex vs Surrey
    </a>
    """

    candidates = extract_crex_match_candidates(
        html,
        base_url="https://crex.com",
        target_league_key=None,
        source="test",
    )

    assert {candidate.league_key for candidate in candidates} == {"ODI Women", "NTB"}


def test_discovery_routes_the_hundred_to_its_dedicated_model_family():
    html = """
    <a href="/cricket-live-score/mil-vs-srl-1st-match-the-hundred-2026-men-match-updates-ZK5">
      Manchester Originals vs Southern Brave
    </a>
    """

    candidates = extract_crex_match_candidates(
        html,
        base_url="https://crex.com",
        target_league_key=None,
        source="test",
    )

    assert len(candidates) == 1
    assert candidates[0].league_key == "Hundred"


def test_discovery_ignores_test_matches():
    html = '<a href="/cricket-live-score/a-vs-b-1st-test-match-updates-XYZ">A vs B Test</a>'
    assert extract_crex_match_candidates(
        html,
        base_url="https://crex.com",
        target_league_key=None,
        source="test",
    ) == []


def test_browser_discovery_configuration_is_safe_when_no_path_is_configured():
    # Rendered discovery must resolve a browser without raising before fetch.
    executable = _browser_executable()
    assert executable is None or isinstance(executable, str)


def test_live_detection_handles_crex_score_and_toss_labels():
    assert _looks_live("BAD 182-7 19.2 28 runs needed in 4 balls")
    assert _looks_live("DEN HUN DEN opt to bat")


def test_live_detection_rejects_completed_score_cards():
    assert _looks_live("GT 155/8 20.0 GT Won Final IPL 2026 RCB 161/5 18.0") is False


def test_discovery_classifies_rendered_shpageeza_t20_as_live():
    html = """
    <a href="/cricket-live-score/amo-vs-mak-18th-match-shpageeza-cricket-league-2026-match-updates-12ZS">
      18th T20, Rahmat Wali Masroor Cricket Ground, Khost AMO 37-3 5.2 MAK Yet to bat AMO opt to bat
    </a>
    """

    candidates = extract_crex_match_candidates(
        html,
        base_url="https://crex.com/cricket-live-score",
        target_league_key=None,
        source="rendered-test",
    )

    assert len(candidates) == 1
    assert candidates[0].league_key == "Shpageeza"
    assert candidates[0].is_live is True


def test_scraper_slate_retires_only_system_predictions_that_are_no_longer_selected():
    class Manager:
        def __init__(self):
            self.stopped = []

        def list_predictions(self, user_id=None):
            assert user_id == SYSTEM_USER_ID
            return [
                {
                    "id": "selected",
                    "league": "T20",
                    "match_url": "https://crex.com/cricket-live-score/a-vs-b-match-updates-1",
                    "status": "running",
                },
                {
                    "id": "obsolete",
                    "league": "T20",
                    "match_url": "https://crex.com/cricket-live-score/c-vs-d-match-updates-2",
                    "status": "running",
                },
            ]

        def stop_match(self, prediction_id, user_id=None):
            assert user_id == SYSTEM_USER_ID
            self.stopped.append(prediction_id)
            return True

    manager = Manager()
    scheduler = AutoPredictionScheduler(manager, Settings())

    scheduler._retire_predictions_outside_scraper_slate([
        MatchCandidate(
            url="https://crex.com/cricket-live-score/a-vs-b-match-updates-1",
            league_key="T20",
            source="scraper:selected",
            is_live=True,
        )
    ])

    assert manager.stopped == ["obsolete"]


def test_scraper_slate_classifies_t20_from_crex_page_title_when_slug_lacks_format(monkeypatch):
    class FakeResponse:
        def __init__(self, *, payload=None, text="", status_code=200):
            self._payload = payload
            self.text = text
            self.status_code = status_code

        def json(self):
            return self._payload

        def raise_for_status(self):
            assert self.status_code < 400

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def get(self, url):
            if url.endswith("/prediction-candidates"):
                return FakeResponse(payload={
                    "matches": [{
                        "url": "https://crex.com/cricket-live-score/aut-vs-rom-3rd-match-eca-mens-european-cup-2026-match-updates-138I",
                        "is_live": True,
                    }]
                })
            return FakeResponse(text="<title>AUT vs ROM, 3rd T20, European Cup 2026 Live</title>")

    monkeypatch.setattr("app.auto_scheduler.httpx.AsyncClient", lambda **kwargs: FakeClient())
    scheduler = AutoPredictionScheduler(
        manager=object(),
        settings=Settings(AUTO_SCRAPER_URL="http://scraper", AUTO_LEAGUE_KEYS="ALL"),
    )

    candidates = asyncio.run(scheduler._discover_from_scraper())

    assert len(candidates) == 1
    assert candidates[0].league_key == "T20"
    assert candidates[0].source == "scraper:selected"
