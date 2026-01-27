"""Tests for prediction storage."""

import json
import pytest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from bbl_pipeline.telegram.storage import (
    PredictionStorage,
    StorageError,
)


@pytest.fixture
def temp_storage():
    """Create a temporary storage instance."""
    with TemporaryDirectory() as tmpdir:
        storage_path = Path(tmpdir) / "test_predictions.jsonl"
        yield PredictionStorage(storage_path)


@pytest.fixture
def sample_prediction():
    """Create a sample prediction record."""
    return {
        "match_id": "1234567",
        "league": "BBL",
        "team_a": "Sydney Sixers",
        "team_b": "Melbourne Stars",
        "selection_type": "BACK",
        "selected_team": "Sydney Sixers",
        "model_probability": 67.5,
        "market_odds": 1.52,
        "model_edge": 5.2,
        "telegram_message_id": 12345,
        "telegram_timestamp": "2026-01-27T10:30:00Z",
        "post_type": "pre_match",
    }


@pytest.fixture
def sample_match_start():
    """Create a sample match start record."""
    return {
        "match_id": "1234567",
        "team_a": "Sydney Sixers",
        "team_b": "Melbourne Stars",
        "toss_winner": "Melbourne Stars",
        "toss_decision": "Bowl",
        "model_prematch_probability": 67.5,
        "telegram_message_id": 12346,
        "telegram_timestamp": "2026-01-27T11:00:00Z",
        "post_type": "match_start",
    }


class TestPredictionStorage:
    """Tests for PredictionStorage class."""
    
    def test_storage_creates_file(self, temp_storage):
        """Test that storage creates the file if it doesn't exist."""
        assert temp_storage.storage_path.exists()
    
    def test_append_record(self, temp_storage, sample_prediction):
        """Test appending a record to storage."""
        temp_storage.append_record(sample_prediction)
        
        # Verify file contains the record
        with open(temp_storage.storage_path) as f:
            content = f.read()
        
        assert "1234567" in content
        assert "Sydney Sixers" in content
        assert "pre_match" in content
    
    def test_append_adds_timestamp(self, temp_storage, sample_prediction):
        """Test that append adds posted_at_utc timestamp."""
        temp_storage.append_record(sample_prediction)
        
        records = temp_storage.read_all_records()
        assert len(records) == 1
        assert "posted_at_utc" in records[0]
    
    def test_append_preserves_existing_timestamp(self, temp_storage, sample_prediction):
        """Test that append preserves existing posted_at_utc."""
        sample_prediction["posted_at_utc"] = "2026-01-27T12:00:00Z"
        temp_storage.append_record(sample_prediction)
        
        records = temp_storage.read_all_records()
        assert records[0]["posted_at_utc"] == "2026-01-27T12:00:00Z"
    
    def test_read_all_records(self, temp_storage, sample_prediction, sample_match_start):
        """Test reading all records from storage."""
        temp_storage.append_record(sample_prediction)
        temp_storage.append_record(sample_match_start)
        
        records = temp_storage.read_all_records()
        
        assert len(records) == 2
        assert records[0]["post_type"] == "pre_match"
        assert records[1]["post_type"] == "match_start"
    
    def test_read_empty_storage(self, temp_storage):
        """Test reading from empty storage."""
        records = temp_storage.read_all_records()
        assert records == []
    
    def test_find_by_match_id(self, temp_storage, sample_prediction, sample_match_start):
        """Test finding records by match ID."""
        temp_storage.append_record(sample_prediction)
        temp_storage.append_record(sample_match_start)
        
        records = temp_storage.find_by_match_id("1234567")
        
        assert len(records) == 2
    
    def test_find_by_match_id_no_match(self, temp_storage, sample_prediction):
        """Test finding records with non-existent match ID."""
        temp_storage.append_record(sample_prediction)
        
        records = temp_storage.find_by_match_id("9999999")
        
        assert len(records) == 0
    
    def test_find_prediction_by_match_id(self, temp_storage, sample_prediction, sample_match_start):
        """Test finding pre-match prediction by match ID."""
        temp_storage.append_record(sample_prediction)
        temp_storage.append_record(sample_match_start)
        
        prediction = temp_storage.find_prediction_by_match_id("1234567")
        
        assert prediction is not None
        assert prediction["post_type"] == "pre_match"
        assert prediction["selection_type"] == "BACK"
    
    def test_find_prediction_not_found(self, temp_storage, sample_match_start):
        """Test finding prediction when none exists."""
        temp_storage.append_record(sample_match_start)
        
        prediction = temp_storage.find_prediction_by_match_id("1234567")
        
        assert prediction is None
    
    def test_count_records(self, temp_storage, sample_prediction, sample_match_start):
        """Test counting records."""
        temp_storage.append_record(sample_prediction)
        temp_storage.append_record(sample_match_start)
        
        assert temp_storage.count_records() == 2
        assert temp_storage.count_records(post_type="pre_match") == 1
        assert temp_storage.count_records(post_type="match_start") == 1
        assert temp_storage.count_records(post_type="result") == 0
    
    def test_get_recent_records(self, temp_storage, sample_prediction, sample_match_start):
        """Test getting recent records."""
        sample_prediction["posted_at_utc"] = "2026-01-27T10:00:00Z"
        sample_match_start["posted_at_utc"] = "2026-01-27T11:00:00Z"
        
        temp_storage.append_record(sample_prediction)
        temp_storage.append_record(sample_match_start)
        
        recent = temp_storage.get_recent_records(limit=1)
        
        assert len(recent) == 1
        assert recent[0]["post_type"] == "match_start"  # More recent
    
    def test_handles_invalid_json_lines(self, temp_storage, sample_prediction):
        """Test that storage handles invalid JSON lines gracefully."""
        # Write a valid record
        temp_storage.append_record(sample_prediction)
        
        # Manually append invalid JSON
        with open(temp_storage.storage_path, "a") as f:
            f.write("invalid json line\n")
        
        # Should still read valid records
        records = temp_storage.read_all_records()
        assert len(records) == 1
    
    def test_unicode_content(self, temp_storage, sample_prediction):
        """Test storage handles unicode content."""
        sample_prediction["team_a"] = "东京队"  # Japanese characters
        sample_prediction["team_b"] = "مومباي"  # Arabic characters
        
        temp_storage.append_record(sample_prediction)
        
        records = temp_storage.read_all_records()
        assert records[0]["team_a"] == "东京队"
        assert records[0]["team_b"] == "مومباي"
