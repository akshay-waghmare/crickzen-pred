"""
Match state logger for recording live prediction data to Parquet.

This module implements the MatchStateLogger class which captures complete match state
(raw state, computed features, calibration chain, market odds) at every ball during
live predictions and persists to per-match Parquet files.

Key features:
- Error isolation: all public methods wrapped in try/except (FR-009)
- Buffered writes: flushes at innings break, match end, or every 30 records
- Deviation computation: model-market gap with bucket/direction classification
- Team tier classification: top/mid/bottom based on feature store win rates
- Schema validation: uses PyArrow schemas for type safety

Primary class: MatchStateLogger
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import structlog

from bbl_pipeline.inference.match_state_schema import (
    BALL_STATE_SCHEMA,
    MATCH_METADATA_SCHEMA,
    get_deviation_bucket,
    get_deviation_direction,
)

logger = structlog.get_logger(__name__)


class MatchStateLogger:
    """
    Records match state data to Parquet during live predictions.
    
    Captures complete prediction context including:
    - Raw match state (runs, wickets, overs, batsmen, bowler, venue)
    - 50+ computed features (resource %, pressure, team strength, rolling stats)
    - Full calibration chain (raw → combined → innings → phase → per-over → league)
    - CREX market odds (back/lay, implied probabilities)
    - Deviation metrics (size, direction, bucket)
    - Team strength tiers
    - Model and feature store versions
    
    All writes are error-isolated to prevent disruption of live predictions (FR-009).
    """
    
    def __init__(
        self,
        match_id: str,
        league: str,
        states_dir: Path,
        model_version: str,
        feature_store_version: str,
    ):
        """
        Initialize match state logger.
        
        Args:
            match_id: Unique match identifier (typically from URL)
            league: League code (bbl, sa20, ilt20, etc.)
            states_dir: Root directory for match states (e.g., data/match_states/<league>/)
            model_version: Model directory basename (e.g., "t20_male_v2")
            feature_store_version: Feature store directory basename
        """
        self.match_id = match_id
        self.league = league
        self.states_dir = Path(states_dir)
        self.model_version = model_version
        self.feature_store_version = feature_store_version
        
        # Create output directory
        self.states_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize buffer
        self.buffer: List[Dict[str, Any]] = []
        self.recording_start = datetime.now()
        self.current_innings = 1
        self.previous_ball_state: Optional[Dict[str, Any]] = None
        self._seen_record_keys: set[tuple[int, int, int, int, int]] = set()
        self.match_file = self.states_dir / f"{self.match_id}.parquet"
        
        # Logging
        self.log = logger.bind(match_id=match_id, league=league)

        # Resume support: load previously recorded keys to avoid rewriting after restart
        self._load_existing_record_keys()
        self.log.info("match_state_logger_initialized", states_dir=str(states_dir))

    def _record_key(self, innings: int, over_number: int, ball_in_over: int, total_runs: int, wickets: int) -> tuple[int, int, int, int, int]:
        """Build stable key for one recorded ball state."""
        return (innings, over_number, ball_in_over, total_runs, wickets)

    def _load_existing_record_keys(self) -> None:
        """Load existing match parquet keys so recording can resume without duplicates."""
        try:
            if not self.match_file.exists():
                return

            existing_df = pd.read_parquet(self.match_file, columns=["innings", "over_number", "ball_in_over", "total_runs", "wickets"])
            for row in existing_df.itertuples(index=False):
                key = self._record_key(
                    int(getattr(row, "innings", 0)),
                    int(getattr(row, "over_number", 0)),
                    int(getattr(row, "ball_in_over", 0)),
                    int(getattr(row, "total_runs", 0)),
                    int(getattr(row, "wickets", 0)),
                )
                self._seen_record_keys.add(key)

            self.log.info("loaded_existing_record_keys", existing_keys=len(self._seen_record_keys), file=str(self.match_file))
        except Exception as e:
            self.log.warning("load_existing_record_keys_failed", error=str(e), file=str(self.match_file))
    
    def _compute_match_phase(self, over_number: int) -> str:
        """
        Classify over number into match phase.
        
        Args:
            over_number: Over number (1-20)
            
        Returns:
            "powerplay" (1-6), "middle" (7-15), or "death" (16-20)
        """
        if over_number <= 6:
            return "powerplay"
        elif over_number <= 15:
            return "middle"
        else:
            return "death"
    
    def _compute_team_tier(self, win_rate: float) -> str:
        """
        Classify team win rate into strength tier.
        
        Uses a simple threshold approach:
        - Top: win_rate >= 0.60
        - Mid: 0.40 <= win_rate < 0.60
        - Bottom: win_rate < 0.40
        
        Args:
            win_rate: Team win rate from feature store (0.0-1.0)
            
        Returns:
            "top", "mid", or "bottom"
        """
        if win_rate >= 0.60:
            return "top"
        elif win_rate >= 0.40:
            return "mid"
        else:
            return "bottom"

    def _team_aliases(self, team: str) -> set[str]:
        """Build comparable aliases for team strings (code/full name, men/women variants)."""
        if not team:
            return set()

        upper = str(team).upper().strip()
        compact = "".join(char for char in upper if char.isalnum())
        aliases = {upper, compact}

        country_code_map = {
            "AUSTRALIA": "AUS",
            "INDIA": "IND",
            "ENGLAND": "ENG",
            "NEWZEALAND": "NZ",
            "SOUTHAFRICA": "SA",
            "PAKISTAN": "PAK",
            "WESTINDIES": "WI",
            "SRILANKA": "SL",
            "BANGLADESH": "BAN",
            "AFGHANISTAN": "AFG",
            "ZIMBABWE": "ZIM",
            "IRELAND": "IRE",
            "SCOTLAND": "SCO",
            "NETHERLANDS": "NED",
            "NAMIBIA": "NAM",
            "CANADA": "CAN",
            "OMAN": "OMA",
            "NEPAL": "NEP",
            "UNITEDARABEMIRATES": "UAE",
            "PAPUANEWGUINEA": "PNG",
            "HONGKONG": "HK",
            "UGANDA": "UGA",
        }

        # Franchise alias map: code → full name (bidirectional)
        franchise_map = {
            # IPL
            "MI": "MUMBAI INDIANS", "CSK": "CHENNAI SUPER KINGS",
            "RCB": "ROYAL CHALLENGERS BENGALURU", "DC": "DELHI CAPITALS",
            "KKR": "KOLKATA KNIGHT RIDERS", "PBKS": "PUNJAB KINGS",
            "RR": "RAJASTHAN ROYALS", "SRH": "SUNRISERS HYDERABAD",
            "GT": "GUJARAT TITANS", "LSG": "LUCKNOW SUPER GIANTS",
            # BBL
            "SS": "SYDNEY SIXERS", "ST": "SYDNEY THUNDER",
            "PS": "PERTH SCORCHERS", "MS": "MELBOURNE STARS",
            "MR": "MELBOURNE RENEGADES", "BH": "BRISBANE HEAT",
            "HH": "HOBART HURRICANES", "AS": "ADELAIDE STRIKERS",
            # SA20
            "MICT": "MI CAPE TOWN", "SEC": "SUNRISERS EASTERN CAPE",
            "JSK": "JOBURG SUPER KINGS", "PR": "PAARL ROYALS",
            "DSG": "DURBAN SUPER GIANTS", "PC": "PRETORIA CAPITALS",
            # PSL
            "IU": "ISLAMABAD UNITED", "KK": "KARACHI KINGS",
            "LQ": "LAHORE QALANDARS", "MS2": "MULTAN SULTANS",
            "PZ": "PESHAWAR ZALMI", "QG": "QUETTA GLADIATORS",
            # ILT20
            "ADKR": "ABU DHABI KNIGHT RIDERS", "DP": "DUBAI CAPITALS",
            "GG": "GULF GIANTS", "DW": "DESERT VIPERS",
            "SH": "SHARJAH WARRIORZ", "MICT2": "MI EMIRATES",
            # WPL
            "RCBW": "ROYAL CHALLENGERS BENGALURU W",
            "DCW": "DELHI CAPITALS W", "MIW": "MUMBAI INDIANS W",
            "GGW": "GUJARAT GIANTS W", "UPWW": "UP WARRIORZ W",
        }
        # Build reverse map: full name → code
        reverse_franchise = {}
        for code, full in franchise_map.items():
            reverse_franchise["".join(c for c in full if c.isalnum())] = code

        # Check if input matches a franchise code
        if upper in franchise_map:
            full_name = franchise_map[upper]
            full_compact = "".join(c for c in full_name if c.isalnum())
            aliases.update({upper, full_name, full_compact})

        # Check if input matches a franchise full name
        if compact in reverse_franchise:
            code = reverse_franchise[compact]
            aliases.update({code, franchise_map[code], compact})

        for country_name, code in country_code_map.items():
            if country_name in compact:
                aliases.update({code, f"{code}W"})

        if compact.endswith("WOMEN"):
            base = compact[:-5]
            aliases.add(base)
            for country_name, code in country_code_map.items():
                if country_name == base:
                    aliases.update({code, f"{code}W"})

        if compact.endswith("W") and len(compact) > 3:
            aliases.add(compact[:-1])

        return {alias for alias in aliases if alias}

    def _teams_match(self, left: str, right: str) -> bool:
        """Return True when two team strings represent the same team."""
        left_aliases = self._team_aliases(left)
        right_aliases = self._team_aliases(right)
        return bool(left_aliases and right_aliases and left_aliases.intersection(right_aliases))
    
    def _map_market_probs(
        self,
        market_fav_team: str,
        market_fav_prob: float,
        batting_team: str,
        bowling_team: str,
    ) -> tuple[Optional[float], Optional[float]]:
        """
        Map market favorite probability to batting/bowling team probabilities.
        
        Args:
            market_fav_team: Which team is market favorite
            market_fav_prob: Implied probability for favorite team
            batting_team: Batting team name
            bowling_team: Bowling team name
            
        Returns:
            (batting_team_prob, bowling_team_prob)
        """
        if self._teams_match(market_fav_team, batting_team):
            return (market_fav_prob, 1.0 - market_fav_prob)
        elif self._teams_match(market_fav_team, bowling_team):
            return (1.0 - market_fav_prob, market_fav_prob)
        else:
            # Market favorite doesn't match either team (shouldn't happen)
            self.log.warning(
                "market_fav_team_mismatch",
                market_fav=market_fav_team,
                batting=batting_team,
                bowling=bowling_team,
                market_aliases=sorted(self._team_aliases(market_fav_team)),
                batting_aliases=sorted(self._team_aliases(batting_team)),
                bowling_aliases=sorted(self._team_aliases(bowling_team)),
            )
            return (None, None)
    
    def _compute_deviation(
        self,
        model_prob: float,
        market_batting_team_prob: Optional[float],
    ) -> tuple[Optional[float], Optional[float], Optional[str], Optional[str]]:
        """
        Compute deviation metrics between model and market.
        
        Args:
            model_prob: Model final probability for batting team
            market_batting_team_prob: Market implied probability for batting team (nullable)
            
        Returns:
            (deviation, deviation_abs, deviation_bucket, deviation_direction)
            All None if market_batting_team_prob is None
        """
        if market_batting_team_prob is None:
            return (None, None, None, None)
        
        deviation = model_prob - market_batting_team_prob
        deviation_abs = abs(deviation)
        deviation_bucket = get_deviation_bucket(deviation_abs)
        deviation_direction = get_deviation_direction(deviation)
        
        return (deviation, deviation_abs, deviation_bucket, deviation_direction)
    
    def record_ball(
        self,
        match_state: Any,  # MatchState dataclass from crex_live_predictor
        features_dict: Dict[str, Any],
        predictor: Any,  # Predictor instance with calibration attributes
        market_odds: Dict[str, Any],
        ensemble_prob: Optional[float] = None,
        ensemble_alpha: Optional[float] = None,
        ensemble_source: Optional[str] = None,
    ) -> None:
        """
        Record one ball state to buffer.
        
        Assembles complete BallStateRecord dict from:
        - match_state: raw state (runs, wickets, overs, batsmen, venue, etc.)
        - features_dict: all computed features from RealTimeFeatureMapper
        - predictor: calibration chain attributes (last_raw_prob, last_calibrated_*, etc.)
        - market_odds: CREX odds dict (market_fav_team, back_odds, fav_prob, etc.)
        - ensemble_prob: blended model+market probability (optional)
        - ensemble_alpha: blending weight used (optional)
        - ensemble_source: "ensemble" or "model_only" (optional)
        
        Computes:
        - model_prob_delta and market_prob_delta from previous ball
        - Deviation metrics (size, bucket, direction)
        - Team strength tiers
        - Match phase
        
        Auto-flushes at 30 records. Entire method wrapped in try/except (FR-009).
        
        Args:
            match_state: MatchState dataclass from predictor
            features_dict: Feature values dict
            predictor: Predictor instance
            market_odds: Market odds dict from CREX
            ensemble_prob: Blended probability (optional)
            ensemble_alpha: Alpha weight used (optional)
            ensemble_source: Source label (optional)
        """
        try:
            # Deduplicate: skip if match state hasn't changed since last record
            overs_val = getattr(match_state, 'overs', 0.0) or 0.0
            runs_val = getattr(match_state, 'total_runs', 0)
            wkts_val = getattr(match_state, 'wickets', 0)
            inn_val = 2 if getattr(match_state, 'is_second_innings', False) else 1
            state_key = (inn_val, overs_val, runs_val, wkts_val)
            if hasattr(self, '_last_state_key') and self._last_state_key == state_key:
                self.log.debug("duplicate_state_skipped", overs=overs_val, runs=runs_val)
                return
            self._last_state_key = state_key

            # Derive over_number, ball_in_over, innings from MatchState
            # MatchState.overs is a float like 5.3 meaning over 5, ball 3
            overs_float = overs_val
            over_int = int(overs_float)
            ball_in_over = int(round((overs_float - over_int) * 10))
            if ball_in_over >= 6:
                ball_in_over = 0
            over_number = over_int + 1  # over 5.3 means ball 3 of over 6 (1-indexed)
            if ball_in_over == 0 and over_int > 0:
                # 5.0 means over 5 completed; represent as ball 6 of over 5 for analysis
                over_number = over_int
                ball_in_over = 6
            elif ball_in_over == 0 and over_int == 0:
                # Start-of-innings snapshot (0.0) -> represent as ball 1 (avoid 0 in analysis keys)
                over_number = 1
                ball_in_over = 1
            
            # Innings already derived above as inn_val
            innings = inn_val

            # Cross-session dedup: skip if this ball state was already persisted in previous runs
            record_key = self._record_key(innings, over_number, ball_in_over, int(runs_val), int(wkts_val))
            if record_key in self._seen_record_keys:
                self.log.debug(
                    "already_recorded_state_skipped",
                    innings=innings,
                    over=over_number,
                    ball=ball_in_over,
                    runs=runs_val,
                    wickets=wkts_val,
                )
                return
            
            # Extract market odds (handle missing gracefully)
            # market_back_odds and market_lay_odds may be strings from MatchState
            market_fav_team = market_odds.get("market_fav_team") or None
            raw_back = market_odds.get("market_back_odds")
            raw_lay = market_odds.get("market_lay_odds")
            try:
                market_back_odds = float(raw_back) if raw_back else None
            except (ValueError, TypeError):
                market_back_odds = None
            try:
                market_lay_odds = float(raw_lay) if raw_lay else None
            except (ValueError, TypeError):
                market_lay_odds = None
            raw_fav_prob = market_odds.get("market_fav_prob")
            try:
                market_fav_prob = float(raw_fav_prob) if raw_fav_prob else None
            except (ValueError, TypeError):
                market_fav_prob = None
            
            # Map market probs to batting/bowling teams
            if market_fav_team and market_fav_prob is not None:
                market_batting_prob, market_bowling_prob = self._map_market_probs(
                    market_fav_team, market_fav_prob, match_state.batting_team, match_state.bowling_team
                )
            else:
                market_batting_prob, market_bowling_prob = None, None
            
            # Get calibration chain from predictor
            model_raw_prob = getattr(predictor, 'last_raw_prob', None)
            model_smoothed_prob = getattr(predictor, 'last_smoothed_prob', None)
            model_calibrated_combined = getattr(predictor, 'last_calibrated_combined', None)
            model_calibrated_innings = getattr(predictor, 'last_calibrated_innings', None)
            model_calibrated_phase = getattr(predictor, 'last_calibrated_phase', None)
            model_calibrated_per_over = getattr(predictor, 'last_calibrated_per_over', None)
            model_league_calibrated = getattr(predictor, 'last_league_calibrated', None)
            model_post_calibrated = getattr(predictor, 'last_post_model_calibration_prob', None)
            model_post_calibration_rule = getattr(predictor, 'last_post_model_calibration_rule', None)
            
            # Final probability (what predictor returns)
            model_final_prob = predictor.last_prediction if hasattr(predictor, 'last_prediction') else model_calibrated_per_over
            
            # Compute deviation
            deviation, deviation_abs, deviation_bucket, deviation_direction = self._compute_deviation(
                model_final_prob, market_batting_prob
            )
            
            # Compute probability deltas from previous ball
            model_prob_delta = None
            market_prob_delta = None
            if self.previous_ball_state:
                prev_model_prob = self.previous_ball_state.get('model_final_prob')
                prev_market_prob = self.previous_ball_state.get('market_batting_team_prob')
                if prev_model_prob is not None:
                    model_prob_delta = model_final_prob - prev_model_prob
                if prev_market_prob is not None and market_batting_prob is not None:
                    market_prob_delta = market_batting_prob - prev_market_prob
            
            # Compute team tiers
            batting_team_wr = features_dict.get('batting_team_win_rate', 0.5)
            bowling_team_wr = features_dict.get('bowling_team_win_rate', 0.5)
            batting_team_tier = self._compute_team_tier(batting_team_wr)
            bowling_team_tier = self._compute_team_tier(bowling_team_wr)
            
            # Compute match phase
            match_phase = self._compute_match_phase(over_number)

            # Bowler fallback: carry forward previous non-empty bowler in same innings
            bowler_name = (getattr(match_state, 'bowler1_name', '') or '').strip()
            if not bowler_name and self.previous_ball_state:
                prev_innings = self.previous_ball_state.get('innings')
                prev_bowler_name = (self.previous_ball_state.get('bowler_name') or '').strip()
                if prev_innings == innings and prev_bowler_name:
                    bowler_name = prev_bowler_name
            
            # Assemble complete record
            record = {
                # Identity
                'match_id': self.match_id,
                'league': self.league,
                'timestamp': datetime.now(),
                'innings': innings,
                'over_number': over_number,
                'ball_in_over': ball_in_over,
                'match_phase': match_phase,
                
                # Raw match state
                'batting_team': match_state.batting_team,
                'bowling_team': match_state.bowling_team,
                'total_runs': getattr(match_state, 'total_runs', 0),
                'wickets': getattr(match_state, 'wickets', 0),
                'overs': overs_float,
                'current_run_rate': getattr(match_state, 'current_run_rate', 0.0),
                'required_run_rate': getattr(match_state, 'required_run_rate', 0.0),
                'target': getattr(match_state, 'target', None),
                'batsman1_name': getattr(match_state, 'batsman1_name', ""),
                'batsman1_runs': getattr(match_state, 'batsman1_runs', 0),
                'batsman1_balls': getattr(match_state, 'batsman1_balls', 0),
                'batsman2_name': getattr(match_state, 'batsman2_name', ""),
                'batsman2_runs': getattr(match_state, 'batsman2_runs', 0),
                'batsman2_balls': getattr(match_state, 'batsman2_balls', 0),
                'bowler_name': bowler_name,
                'venue': match_state.venue,
                'toss_winner': match_state.toss_winner if hasattr(match_state, 'toss_winner') else "",
                'toss_decision': match_state.toss_decision if hasattr(match_state, 'toss_decision') else "",
                
                # Computed features (all from features_dict)
                **{k: features_dict.get(k) for k in [
                    'resource_pct', 'resource_win_prob', 'expected_final_score', 'projected_score',
                    'projected_vs_venue_avg', 'score_vs_par', 'pressure_index', 'dls_pressure_index',
                    'team_strength_diff', 'batting_team_win_rate', 'bowling_team_win_rate',
                    'batting_team_situation_wr', 'bowling_team_situation_wr', 'situation_advantage',
                    'runs_last_12', 'runs_last_18', 'wickets_last_12', 'wickets_last_30',
                    'boundary_pct_last_18', 'chase_difficulty', 'score_per_wicket',
                    'wickets_times_balls', 'rrr_times_wickets', 'batting_pair_strength',
                    'acceleration_potential', 'crr_times_res', 'resources_remaining',
                    'run_rate_diff', 'is_powerplay', 'is_death', 'venue_avg_score',
                    'venue_avg_wickets', 'venue_bat_first_wr', 'batsman_venue_avg',
                    'batsman_venue_sr', 'batsman_vs_team_avg', 'bowler_venue_econ',
                    'bowler_venue_sr', 'bowler_vs_team_econ',
                ]},
                
                # Calibration chain
                'model_raw_prob': model_raw_prob,
                'model_smoothed_prob': model_smoothed_prob,
                'model_calibrated_combined': model_calibrated_combined,
                'model_calibrated_innings': model_calibrated_innings,
                'model_calibrated_phase': model_calibrated_phase,
                'model_calibrated_per_over': model_calibrated_per_over,
                'model_league_calibrated': model_league_calibrated,
                'model_post_calibrated': model_post_calibrated,
                'model_post_calibration_rule': model_post_calibration_rule,
                'model_final_prob': model_final_prob,
                
                # Market odds
                'market_fav_team': market_fav_team,
                'market_back_odds': market_back_odds,
                'market_lay_odds': market_lay_odds,
                'market_fav_prob': market_fav_prob,
                'market_batting_team_prob': market_batting_prob,
                'market_bowling_team_prob': market_bowling_prob,
                
                # Deviation metrics
                'deviation': deviation,
                'deviation_abs': deviation_abs,
                'deviation_bucket': deviation_bucket,
                'deviation_direction': deviation_direction,
                'model_prob_delta': model_prob_delta,
                'market_prob_delta': market_prob_delta,
                
                # Team strength tier
                'batting_team_tier': batting_team_tier,
                'bowling_team_tier': bowling_team_tier,
                
                # Ensemble blending
                'ensemble_prob': ensemble_prob,
                'ensemble_alpha': ensemble_alpha,
                'ensemble_source': ensemble_source,
                
                # Versioning
                'model_version': self.model_version,
                'feature_store_version': self.feature_store_version,
            }
            
            # Append to buffer
            self.buffer.append(record)
            self._seen_record_keys.add(record_key)
            self.previous_ball_state = record
            
            # Check for innings change
            if innings != self.current_innings:
                self.log.info("innings_break_detected", innings=innings)
                self.flush()
                self.current_innings = innings
            
            # Auto-flush at 30 records
            if len(self.buffer) >= 30:
                self.log.info("auto_flush_triggered", buffer_size=len(self.buffer))
                self.flush()
            
            self.log.debug("ball_recorded", buffer_size=len(self.buffer))
            
        except Exception as e:
            self.log.error("record_ball_failed", error=str(e), exc_info=True)
            # Error is logged but not raised (FR-009)
    
    def flush(self) -> None:
        """
        Flush buffered records to Parquet file.
        
        Writes buffer to <match_id>.parquet using BALL_STATE_SCHEMA.
        If file already exists, appends new records.
        Clears buffer after successful write.
        
        Wrapped in try/except (FR-009).
        """
        try:
            if not self.buffer:
                self.log.debug("flush_skipped_empty_buffer")
                return
            
            # Convert buffer to DataFrame
            df = pd.DataFrame(self.buffer)
            
            # Convert to PyArrow Table with schema
            try:
                table = pa.Table.from_pandas(df, schema=BALL_STATE_SCHEMA)
            except Exception as schema_error:
                self.log.warning("schema_validation_failed_using_inferred", error=str(schema_error))
                table = pa.Table.from_pandas(df)
            
            # Write to Parquet
            match_file = self.match_file

            if match_file.exists():
                # Append to existing file; use promote_options to handle schema evolution
                # (e.g. old rows have string, new rows have null for optional columns)
                existing_table = pq.read_table(match_file)
                try:
                    combined_table = pa.concat_tables([existing_table, table], promote_options="permissive")
                except Exception:
                    # Fallback: unify to common schema by casting to BALL_STATE_SCHEMA
                    combined_table = pa.concat_tables([existing_table, table], promote_options="default")
                pq.write_table(combined_table, match_file)
                self.log.info("buffer_appended_to_existing_file", rows=len(df), file=str(match_file))
            else:
                # Write new file
                pq.write_table(table, match_file)
                self.log.info("buffer_flushed_to_new_file", rows=len(df), file=str(match_file))
            
            # Clear buffer
            self.buffer = []
            
        except Exception as e:
            self.log.error("flush_failed", error=str(e), buffer_size=len(self.buffer), exc_info=True)
            # Error is logged but not raised (FR-009)
    
    def finalize(
        self,
        winner: Optional[str] = None,
        team_a_score: Optional[str] = None,
        team_b_score: Optional[str] = None,
        result_type: str = "in_progress",
    ) -> None:
        """
        Finalize match recording and write metadata.
        
        Flushes any remaining buffer, then writes/appends match metadata row
        to match_metadata.parquet.
        
        Wrapped in try/except (FR-009).
        
        Args:
            winner: Match winner team name (None if no result)
            team_a_score: Team A score string (e.g., "185/4")
            team_b_score: Team B score string
            result_type: "completed", "no_result", or "in_progress"
        """
        try:
            # Flush remaining buffer
            self.flush()
            
            # Prepare metadata record
            recording_end = datetime.now()
            
            # Extract teams from first recorded ball (if buffer was flushed, read from file)
            team_a = None
            team_b = None
            team_a_tier = None
            team_b_tier = None
            venue = None
            toss_winner = None
            toss_decision = None
            
            match_file = self.states_dir / f"{self.match_id}.parquet"
            if match_file.exists():
                df = pd.read_parquet(match_file)
                if not df.empty:
                    first_row = df.iloc[0]
                    # Team A = team batting first (innings 1)
                    innings_1_rows = df[df['innings'] == 1]
                    if not innings_1_rows.empty:
                        team_a = innings_1_rows.iloc[0]['batting_team']
                        team_a_tier = innings_1_rows.iloc[0]['batting_team_tier']
                    innings_2_rows = df[df['innings'] == 2]
                    if not innings_2_rows.empty:
                        team_b = innings_2_rows.iloc[0]['batting_team']
                        team_b_tier = innings_2_rows.iloc[0]['batting_team_tier']
                    venue = first_row.get('venue')
                    toss_winner = first_row.get('toss_winner')
                    toss_decision = first_row.get('toss_decision')
                    total_balls = len(df)
            else:
                total_balls = 0
            
            metadata_record = {
                'match_id': self.match_id,
                'match_url': "",  # Populated by caller if available
                'league': self.league,
                'date': self.recording_start,
                'venue': venue or "",
                'team_a': team_a or "",
                'team_b': team_b or "",
                'team_a_tier': team_a_tier or "mid",
                'team_b_tier': team_b_tier or "mid",
                'toss_winner': toss_winner or "",
                'toss_decision': toss_decision or "",
                'winner': winner,
                'team_a_score': team_a_score,
                'team_b_score': team_b_score,
                'result_type': result_type,
                'model_version': self.model_version,
                'feature_store_version': self.feature_store_version,
                'total_balls_recorded': total_balls,
                'recording_start': self.recording_start,
                'recording_end': recording_end,
            }
            
            # Write/append to metadata file
            metadata_file = self.states_dir / "match_metadata.parquet"
            metadata_df = pd.DataFrame([metadata_record])
            
            try:
                metadata_table = pa.Table.from_pandas(metadata_df, schema=MATCH_METADATA_SCHEMA)
            except Exception as schema_error:
                self.log.warning("metadata_schema_validation_failed", error=str(schema_error))
                metadata_table = pa.Table.from_pandas(metadata_df)
            
            if metadata_file.exists():
                existing_metadata = pq.read_table(metadata_file)
                combined_metadata = pa.concat_tables([existing_metadata, metadata_table])
                pq.write_table(combined_metadata, metadata_file)
                self.log.info("metadata_appended", file=str(metadata_file))
            else:
                pq.write_table(metadata_table, metadata_file)
                self.log.info("metadata_created", file=str(metadata_file))
            
            self.log.info(
                "match_recording_finalized",
                winner=winner,
                balls_recorded=total_balls,
                duration_seconds=(recording_end - self.recording_start).total_seconds(),
            )
            
        except Exception as e:
            self.log.error("finalize_failed", error=str(e), exc_info=True)
            # Error is logged but not raised (FR-009)
