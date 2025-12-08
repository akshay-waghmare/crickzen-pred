import pandera as pa
from pandera.typing import Series

class MatchSchema(pa.DataFrameModel):
    """
    Pandera schema for the processed ball-by-ball match data.
    """
    match_id: Series[str] = pa.Field(nullable=False, description="Unique Cricsheet Match ID")
    season: Series[str] = pa.Field(nullable=False, description="Season Year (e.g., '2023/24')")
    date: Series[pa.DateTime] = pa.Field(nullable=False, description="Match Date")
    venue_id: Series[str] = pa.Field(nullable=False, description="Canonical Venue ID")
    batting_team_id: Series[str] = pa.Field(nullable=False, description="Canonical Team ID")
    bowling_team_id: Series[str] = pa.Field(nullable=False, description="Canonical Team ID")
    innings: Series[int] = pa.Field(ge=1, le=4, description="Innings Number (1 or 2 usually)")
    over: Series[int] = pa.Field(ge=0, description="Over Number (0-19 for T20)")
    ball: Series[int] = pa.Field(ge=1, description="Ball Number within Over")
    batter_id: Series[str] = pa.Field(nullable=False, description="Canonical Batter ID")
    bowler_id: Series[str] = pa.Field(nullable=False, description="Canonical Bowler ID")
    non_striker_id: Series[str] = pa.Field(nullable=False, description="Canonical Non-Striker ID")
    runs_batter: Series[int] = pa.Field(ge=0, description="Runs off bat")
    runs_extras: Series[int] = pa.Field(ge=0, description="Extra runs")
    runs_total: Series[int] = pa.Field(ge=0, description="Total runs for the ball")
    wicket_type: Series[str] = pa.Field(nullable=True, description="Type of dismissal (if any)")
    player_out_id: Series[str] = pa.Field(nullable=True, description="ID of player dismissed")
    is_super_over: Series[bool] = pa.Field(nullable=False, description="Flag for Super Over")

    class Config:
        strict = True # Reject columns not in schema
        coerce = True # Attempt to convert types
