"""Tests for legal-ball normalization and Hundred structural coordinates."""

from bbl_pipeline.ingestion.hundred_normalizer import HundredNormalizer


def _delivery(label: str, *, extras=None, total: int = 0) -> dict:
    return {
        "actual_delivery": label,
        "batter": "Batter",
        "bowler": "Bowler",
        "non_striker": "Partner",
        "runs": {"batter": total, "extras": 0, "total": total},
        **({"extras": extras} if extras is not None else {}),
    }


def test_illegal_deliveries_do_not_advance_legal_clock() -> None:
    innings = {
        "team": "Team A",
        "overs": [{
            "over": 0,
            "deliveries": [
                _delivery("0.1"),
                _delivery("0.2", extras={"wides": 1}, total=1),
                _delivery("0.2"),
                _delivery("0.3", extras={"noballs": 1}, total=1),
                _delivery("0.3"),
            ],
        }],
    }

    result = HundredNormalizer().normalize_innings(innings, match_id="m1")

    assert result.legal_balls == 3
    assert [row["legal_ball_index"] for row in result.rows] == [1, None, 2, None, 3]
    assert [row["balls_remaining"] for row in result.rows] == [99, 99, 98, 98, 97]


def test_phase_powerplay_and_end_block_use_legal_balls() -> None:
    deliveries = []
    for over in range(20):
        deliveries.append({
            "over": over,
            "deliveries": [_delivery(f"{over}.{ball}") for ball in range(1, 6)],
        })

    result = HundredNormalizer().normalize_innings({"overs": deliveries}, match_id="m2")
    legal_rows = [row for row in result.rows if row["is_legal_delivery"]]

    assert result.legal_balls == 100
    assert legal_rows[0]["five_index"] == 1
    assert legal_rows[24]["powerplay_active"] is True
    assert legal_rows[25]["powerplay_active"] is False
    assert legal_rows[24]["phase"] == "powerplay"
    assert legal_rows[25]["phase"] == "middle"
    assert legal_rows[59]["end_block_index"] == 6
    assert legal_rows[60]["end_block_index"] == 7
    assert legal_rows[84]["phase"] == "death"
    assert legal_rows[85]["phase"] == "final"
    assert legal_rows[99]["ball_within_five"] == 5


def test_raw_six_ball_label_is_flagged_without_changing_clock() -> None:
    innings = {
        "overs": [{
            "over": 0,
            "deliveries": [_delivery("0.1"), _delivery("0.6")],
        }],
    }

    result = HundredNormalizer().normalize_innings(innings, match_id="m3")

    assert result.legal_balls == 2
    assert "raw_ball_label_exceeds_set_size" in result.anomaly_flags
    assert [row["legal_ball_index"] for row in result.rows] == [1, 2]


def test_overflow_and_super_five_are_explicit_anomalies() -> None:
    innings = {
        "overs": [{
            "over": 0,
            "deliveries": [_delivery(f"0.{i}") for i in range(1, 102)],
        }],
    }

    result = HundredNormalizer().normalize_innings(
        innings, match_id="m4", innings_number=1, is_super_five=True
    )

    assert result.legal_balls == 101
    assert "legal_ball_overflow" in result.anomaly_flags
    assert "super_five" in result.anomaly_flags
    assert result.rows[-1]["legal_ball_index"] is None

