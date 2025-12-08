import pytest
from pathlib import Path
import json
from bbl_pipeline.ingestion.loader import load_match_file
from bbl_pipeline.ingestion.processor import process_match, extract_match_metadata

@pytest.fixture
def sample_match_json(tmp_path):
    data = {
        "info": {
            "dates": ["2023-01-01"],
            "teams": ["Team A", "Team B"],
            "venue": "Test Venue",
            "season": "2023/24",
            "match_type": "T20"
        },
        "innings": [
            {
                "team": "Team A",
                "overs": [
                    {
                        "over": 0,
                        "deliveries": [
                            {
                                "batter": "Batter A",
                                "bowler": "Bowler B",
                                "non_striker": "NonStriker A",
                                "runs": {"batter": 1, "extras": 0, "total": 1},
                                "wickets": [{"kind": "caught", "player_out": "Batter A"}]
                            }
                        ]
                    }
                ]
            },
            {
                "team": "Team B",
                "overs": []
            }
        ]
    }
    p = tmp_path / "match.json"
    with open(p, "w") as f:
        json.dump(data, f)
    return p

def test_load_match_file(sample_match_json):
    data = load_match_file(sample_match_json)
    assert data["info"]["venue"] == "Test Venue"

def test_extract_match_metadata(sample_match_json):
    data = load_match_file(sample_match_json)
    meta = extract_match_metadata(data, "match_1")
    assert meta["match_id"] == "match_1"
    assert meta["season"] == "2023/24"
    assert meta["team_a"] == "Team A"

def test_process_match(sample_match_json):
    data = load_match_file(sample_match_json)
    main, super_over = process_match(data, "match_1")
    
    assert len(main) == 1
    assert len(super_over) == 0
    
    row = main[0]
    assert row["batter_id"] == "Batter A"
    assert row["runs_batter"] == 1
    assert row["wicket_type"] == "caught"
    assert row["innings"] == 1
    assert row["ball"] == 1
    assert row["over"] == 0
    assert row["is_super_over"] is False

def test_super_over_detection():
    data = {
        "info": {"match_type": "T20", "dates": ["2023-01-01"]},
        "innings": [
            {"team": "A", "overs": []},
            {"team": "B", "overs": []},
            {
                "team": "A", 
                "super_over": True,
                "overs": [{"over": 0, "deliveries": [{"batter": "X", "runs": {"total": 6}}]}]
            }
        ]
    }
    main, super_over = process_match(data, "match_so")
    
    assert len(main) == 0
    assert len(super_over) == 1
    assert super_over[0]["is_super_over"] is True
