from app.public import PublicMatchService, serialize_prediction


def test_public_payload_exposes_safe_intelligence_metrics():
    state = {
        "format": "odi",
        "model_dir": "C:/project/models/odi_all_v2",
        "score": 228,
        "wickets": 4,
        "overs": 42.0,
        "batting_team": "New Zealand",
        "bowling_team": "West Indies",
        "features": {
            "expected_final_score": 295.9,
            "projected_score": 271.4,
            "current_run_rate": 5.43,
            "required_run_rate": 0.0,
            "venue_avg_score": 257.7,
            "resource_pct": 19.2,
            "resource_win_prob": 0.61,
            "score_vs_par": -3.0,
            "pressure_index": 0.12,
        },
        "chart_history": [
            {"overs": 20, "score": 100, "wickets": 2, "bat_win_prob": 0.52, "expected_final_score": 282.4, "projected_score": 260},
            {"overs": 40, "score": 215, "wickets": 4, "bat_win_prob": 0.61, "expected_final_score": 295.9, "projected_score": 271.4},
        ],
    }

    payload = serialize_prediction(
        prediction_id="test-id",
        match_url="https://crex.com/cricket-live-score/nz-vs-wi-1st-odi-match-updates-TEST",
        league="ODI Male",
        status="running",
        state=state,
    )

    assert payload.expected_final_score == 296
    assert payload.projected_score == 271
    assert payload.venue_average_score == 257.7
    assert payload.resource_win_probability_pct == 61
    assert payload.score_vs_par == -3.0
    assert len(payload.last_swings) == 2
    assert len(payload.prediction_history) == 2
    assert payload.prediction_history[-1].expected_final_score == 296
    assert payload.prediction_history[-1].projected_score == 271
    assert payload.prediction_history[-1].win_probability_pct == 61
    assert payload.reasons
    assert any("below" in reason for reason in payload.reasons)
    assert payload.explanation_pack["expected_score"] == 296
    assert payload.explanation_pack["turning_point"]["over"] == "40"
    assert payload.match_url == "https://crex.com/cricket-live-score/nz-vs-wi-1st-odi-match-updates-TEST"
    assert not hasattr(payload, "features")


def test_public_payload_handles_unavailable_model_state():
    payload = serialize_prediction(
        prediction_id="test-id",
        match_url="https://crex.com/cricket-live-score/nz-vs-wi-1st-odi-match-updates-TEST",
        league="ODI Male",
        status="running",
        state=None,
    )

    assert payload.expected_final_score is None
    assert payload.resource_win_probability_pct is None
    assert payload.last_swings == []
    assert payload.prediction_history == []
    assert payload.reasons == []


def test_public_detail_keeps_full_probability_history_without_inflating_match_list():
    history = [
        {
            "overs": f"{index // 6}.{index % 6}",
            "score": index,
            "wickets": 0,
            "bat_win_prob": 0.45 + (index / 1000),
            "innings": 1,
        }
        for index in range(40)
    ]
    state = {
        "format": "t20",
        "score": 39,
        "wickets": 0,
        "overs": 6.3,
        "batting_team": "A",
        "bowling_team": "B",
        "history": history,
    }

    summary = serialize_prediction(
        prediction_id="history-summary",
        match_url="https://crex.com/cricket-live-score/a-vs-b-match-updates-HISTORY",
        league="T20",
        status="running",
        state=state,
    )
    detail = serialize_prediction(
        prediction_id="history-detail",
        match_url="https://crex.com/cricket-live-score/a-vs-b-match-updates-HISTORY",
        league="T20",
        status="running",
        state=state,
        detail=True,
    )

    assert len(summary.prediction_history) == 24
    assert len(detail.prediction_history) == 40
    assert detail.prediction_history[0].win_probability_pct == 45


def test_live_candidate_without_a_running_predictor_is_not_publicly_listed():
    class Manager:
        def list_predictions(self):
            return []

    class Scheduler:
        def status(self):
            return {
                "last_candidates": [
                    {
                        "url": "https://crex.com/cricket-live-score/a-vs-b-match-updates-1",
                        "league": "T20",
                        "source": "scraper:selected",
                        "label": "A vs B",
                        "is_live": True,
                    },
                    {
                        "url": "https://crex.com/cricket-live-score/c-vs-d-match-updates-2",
                        "league": "T20",
                        "source": "scraper:selected",
                        "label": "C vs D",
                        "is_live": False,
                    },
                ]
            }

    rows = PublicMatchService(manager=Manager(), scheduler=Scheduler()).list_matches()

    assert [row.title for row in rows] == ["C vs D"]


def test_running_prediction_without_state_is_not_publicly_listed():
    class Prediction:
        output_json_path = "unused.json"

        def read_state(self):
            return None

    class Manager:
        def list_predictions(self):
            return [{"id": "pending", "status": "running", "match_url": "https://crex.com/cricket-live-score/a-vs-b-match-updates-1"}]

        def get_prediction(self, prediction_id):
            return Prediction()

    rows = PublicMatchService(manager=Manager()).list_matches()

    assert rows == []
