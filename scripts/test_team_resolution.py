"""Test team resolution for BPL teams."""
from src.bbl_pipeline.features.store import InMemoryFeatureStore

store = InMemoryFeatureStore(
    'data/bpl_feature_store_v1/player_stats.parquet',
    'data/bpl_feature_store_v1/venue_stats.parquet'
)
store.load()

teams = ['NE', 'RW', 'Noakhali Express', 'Rajshahi Warriors']

for t in teams:
    stats = store.get_team_stats(t)
    if stats:
        print(f"{t}: win_rate={stats['win_rate']:.3f}")
    else:
        print(f"{t}: NOT FOUND")
