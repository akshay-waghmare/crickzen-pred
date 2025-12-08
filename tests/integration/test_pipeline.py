import pytest
from pathlib import Path
import json
import pandas as pd
from click.testing import CliRunner
from bbl_pipeline.cli import main

@pytest.fixture
def sample_data(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    
    # Create a sample match file
    match_data = {
        "info": {
            "dates": ["2023-01-01"],
            "season": "2023",
            "teams": ["Team A", "Team B"],
            "venue": "Test Venue",
            "gender": "male",
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
                                "batter": "Player 1",
                                "bowler": "Player 2",
                                "non_striker": "Player 3",
                                "runs": {"batter": 1, "extras": 0, "total": 1}
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
    
    with open(input_dir / "123456.json", "w") as f:
        json.dump(match_data, f)
        
    return input_dir

def test_full_pipeline(tmp_path, sample_data):
    runner = CliRunner()
    output_dir = tmp_path / "output"
    
    # Create config file
    config_path = tmp_path / "config.yaml"
    with open(config_path, "w") as f:
        f.write(f"input_dir: {sample_data}\noutput_dir: {output_dir}\nlog_level: INFO\n")

    # 1. Ingest
    result = runner.invoke(main, ['--config', str(config_path), 'ingest'])
    if result.exit_code != 0:
        print("Ingest failed:")
        print(result.output)
        print(result.exception)
        import traceback
        traceback.print_tb(result.exc_info[2])
    assert result.exit_code == 0
    
    # Verify output
    matches_path = output_dir / "matches"
    assert matches_path.exists()
    
    # Check partition
    season_path = matches_path / "season=2023"
    assert season_path.exists()
    
    files = list(season_path.glob("*.parquet"))
    assert len(files) > 0
    
    df = pd.read_parquet(files[0])
    assert len(df) == 1
    assert df.iloc[0]['match_id'] == "123456"
    assert df.iloc[0]['batter_id'] == "Player 1" # Should be name if not resolved
    
    # 2. Resolve (Scan)
    result = runner.invoke(main, ['--config', str(config_path), 'resolve'])
    assert result.exit_code == 0
    assert "Entity Resolution Report" in result.output
    
    # 3. Validate
    result = runner.invoke(main, ['--config', str(config_path), 'validate'])
    assert result.exit_code == 0
    # Check for success message (might be in logs which are captured by structlog/click?)
    # Since we configured logging to stdout/stderr, click runner captures it.
    # But structlog might be configured differently in tests.
    # We check exit code mainly.
