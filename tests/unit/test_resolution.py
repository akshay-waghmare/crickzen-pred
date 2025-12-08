import pytest
from pathlib import Path
from bbl_pipeline.processing.registry import EntityRegistry
from bbl_pipeline.processing.resolution import EntityResolver

@pytest.fixture
def registry(tmp_path):
    # Create a temporary registry file
    reg_path = tmp_path / "registry.yaml"
    # We can initialize an empty registry and add some data manually for testing
    reg = EntityRegistry(reg_path)
    
    # Add some mock data
    # Note: In T008 implementation, players is a dict of id -> data
    # But EntityResolver uses registry.players directly.
    reg.players = {
        "p1": {"id": "p1", "name": "Glenn Maxwell", "other_names": ["G. Maxwell", "Maxwell, G."]},
        "p2": {"id": "p2", "name": "Aaron Finch", "other_names": ["A. Finch"]}
    }
    reg.teams = {
        "t1": {"id": "t1", "name": "Melbourne Stars", "other_names": ["Stars"]},
        "t2": {"id": "t2", "name": "Melbourne Renegades", "other_names": ["Renegades"]}
    }
    reg.venues = {
        "v1": {"id": "v1", "name": "The Gabba", "other_names": ["Brisbane Cricket Ground"]}
    }
    return reg

@pytest.fixture
def resolver(registry):
    return EntityResolver(registry)

def test_resolve_player_exact(resolver):
    pid, score = resolver.resolve_player("Glenn Maxwell")
    assert pid == "p1"
    assert score == 100.0

def test_resolve_player_alias(resolver):
    pid, score = resolver.resolve_player("G. Maxwell")
    assert pid == "p1"
    assert score == 100.0

def test_resolve_player_fuzzy(resolver):
    # "Glen Maxwell" (typo)
    pid, score = resolver.resolve_player("Glen Maxwell")
    assert pid == "p1"
    assert score > 90.0

def test_resolve_player_unknown(resolver):
    pid, score = resolver.resolve_player("Unknown Player")
    assert pid is None
    # Score might be low but not None, but pid is None if below threshold

def test_resolve_team(resolver):
    tid, score = resolver.resolve_team("Stars")
    assert tid == "t1"
    
    tid, score = resolver.resolve_team("Melbourne Stars")
    assert tid == "t1"

def test_resolve_venue(resolver):
    vid, score = resolver.resolve_venue("The Gabba")
    assert vid == "v1"
    
    vid, score = resolver.resolve_venue("Brisbane Cricket Ground")
    assert vid == "v1"
