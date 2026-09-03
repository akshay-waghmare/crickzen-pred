"""
Crex Live Match Predictor

Uses the existing Crex scraper to get live match data and runs predictions.
Optionally outputs state to a JSON file for Streamlit integration.
Includes Monte Carlo simulation for uncertainty quantification.
"""

import asyncio
import sys
import os
import re
import json
import structlog
from pathlib import Path
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from urllib.parse import quote

# Force UTF-8 stdout on Windows to avoid charmap encoding crashes with emoji
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PROJECT_SRC = Path(__file__).resolve().parents[2]
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from bbl_pipeline.features.format_config import FormatConfig

logger = structlog.get_logger()

# Monte Carlo simulation imports
try:
    from bbl_pipeline.simulation import (
        MatchState as SimMatchState,
        simulate,
        simulate_one_over,
        simulate_two_overs,
        simulate_five_overs,
        evaluate_bet,
        BettingThresholds,
    )
    SIMULATION_AVAILABLE = True
except ImportError:
    SIMULATION_AVAILABLE = False
    logger.warning("Monte Carlo simulation module not available")

# Add scraper to path
SCRAPER_PATH = Path(__file__).parent.parent.parent.parent.parent / "scraper" / "crex_scraper_python"
sys.path.insert(0, str(SCRAPER_PATH))

from playwright.async_api import async_playwright, BrowserContext, Page


@dataclass
class BallData:
    """Data for a single ball delivery."""
    ball_number: str  # e.g., "8.3"
    over_number: int
    ball_in_over: int
    runs: int
    is_wicket: bool
    is_dot: bool
    is_boundary: bool
    is_six: bool
    extras: int
    extras_type: Optional[str]
    commentary: str
    batsman_name: str
    bowler_name: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass  
class MatchState:
    """Current match state for predictions."""
    batting_team: str = ""
    bowling_team: str = ""
    total_runs: int = 0
    wickets: int = 0
    overs: float = 0.0
    current_run_rate: float = 0.0
    required_run_rate: float = 0.0
    target: Optional[int] = None
    is_second_innings: bool = False
    batsman1_name: str = ""
    batsman1_runs: int = 0
    batsman1_balls: int = 0
    batsman2_name: str = ""
    batsman2_runs: int = 0
    batsman2_balls: int = 0
    bowler1_name: str = ""
    bowler1_overs: float = 0.0
    bowler1_runs: int = 0
    bowler1_wickets: int = 0
    bowler_data_source: str = ""
    venue: str = ""
    toss_winner: str = ""
    toss_decision: str = ""
    balls_data: List[BallData] = field(default_factory=list)
    # Market odds from CREX API
    market_fav_team: str = ""
    market_back_odds: str = ""
    market_lay_odds: str = ""
    market_fav_prob: float = 0.0  # Implied probability from back odds


def blend_predictions(
    model_prob: float,
    market_prob: Optional[float],
    market_age_seconds: Optional[float],
    alpha: float,
    staleness_threshold: float = 60.0,
) -> Tuple[float, str]:
    """Blend model and market predictions with graceful fallback.

    Args:
        model_prob: Model-predicted win probability for batting team.
        market_prob: Market-implied win probability (None if unavailable).
        market_age_seconds: Seconds since last market update (None if unknown).
        alpha: Blending weight — 1.0 = pure model, 0.0 = pure market.
        staleness_threshold: Maximum acceptable market age in seconds.

    Returns:
        (blended_probability, source) where source is "ensemble" or "model_only".
    """
    try:
        import math as _math
        # Validate model_prob
        if model_prob is None or not isinstance(model_prob, (int, float)):
            return (0.5, "model_only")
        if _math.isnan(float(model_prob)):
            return (0.5, "model_only")
        model_prob = max(0.001, min(0.999, float(model_prob)))

        # Check market data availability
        if market_prob is None:
            return (model_prob, "model_only")
        if not isinstance(market_prob, (int, float)):
            return (model_prob, "model_only")
        market_prob = float(market_prob)
        if _math.isnan(market_prob) or market_prob < 0 or market_prob > 1:
            return (model_prob, "model_only")

        # Check staleness
        if market_age_seconds is None:
            return (model_prob, "model_only")
        if not isinstance(market_age_seconds, (int, float)):
            return (model_prob, "model_only")
        if float(market_age_seconds) > staleness_threshold:
            return (model_prob, "model_only")

        # Blend
        ensemble = alpha * model_prob + (1 - alpha) * market_prob
        ensemble = max(0.001, min(0.999, ensemble))
        return (ensemble, "ensemble")
    except Exception:
        # FR-012: never raise
        try:
            return (max(0.001, min(0.999, float(model_prob))), "model_only")
        except Exception:
            return (0.5, "model_only")


class CrexLivePredictor:
    """
    Live match predictor using Crex scraper data.
    Optionally writes state to JSON for Streamlit integration.
    """
    
    def __init__(self, match_url: str, model_dir: str, headless: bool = True,
                 feature_store_dir: str = None, output_json: str = None,
                 live_match_json: str = None, venue: str = None, league: str = None,
                 odm_model_dir: str = None,
                 use_ml_model: bool = False, record_states: bool = False, states_dir: str = None,
                 total_overs: int = None, revised_target: int = None, mc_only: bool = False,
                 market_stack_model_dir: str = None, team1_name: str = None, team2_name: str = None,
                 candidate_model_dir: str = None):
        self.original_match_url = match_url
        self.match_url = self._normalize_live_url(match_url)
        # The scraper/backend schedule is authoritative for the current
        # provider match. URL abbreviations are not globally unique (DG is a
        # valid code for Dhaka Gladiators in one competition and Dublin
        # Guardians in another), so retain the explicit pair when supplied.
        self._team1_name_hint = str(team1_name or '').strip()
        self._team2_name_hint = str(team2_name or '').strip()
        self.model_dir = model_dir
        self.headless = headless
        self.feature_store_dir = feature_store_dir
        self.league = league  # League code for league-specific calibration
        self.use_ml_model = use_ml_model  # Use ML model for Monte Carlo terminal evaluation
        self.record_states = record_states  # Enable match state recording
        self.states_dir = states_dir  # Custom states directory
        self.output_json = output_json  # Path for JSON output (for Streamlit)
        self.venue_override = venue
        self.mc_only = mc_only  # Force MC-only mode even for 20-over matches
        self.market_stack_model_dir_override = market_stack_model_dir
        self.candidate_model_dir = candidate_model_dir
        self.candidate_predictor = None
        self.last_candidate_prob = None
        self.candidate_model_version = Path(candidate_model_dir).name if candidate_model_dir else ""
        self.candidate_artifact_sha256 = ""
        self.candidate_feature_order_sha256 = ""
        self.candidate_source_revision = ""

        league_code = (league or "").lower()
        default_odm_model_dir = "models/odm_v1" if league_code in {"ipl", "psl"} and not mc_only else None
        self.odm_model_dir = odm_model_dir or default_odm_model_dir

        # Reduced-over support
        self._cli_total_overs = total_overs  # CLI override (None = auto-detect or default 20)
        self._cli_revised_target = revised_target  # CLI override for DLS revised target
        self._effective_total_overs = total_overs  # Currently effective total overs (may change mid-match)

        # Create format config based on total_overs
        if total_overs is not None and 1 <= total_overs < 20:
            self.format_config = FormatConfig.t20_reduced(total_overs)
            logger.info(f"Reduced-over mode: {total_overs} overs, par={self.format_config.par_score:.1f}")
        elif total_overs is not None and total_overs >= 40:
            # ODI format (40-50 overs) - detect gender from league
            odi_gender = "female" if league and "female" in league else "male"
            self.format_config = FormatConfig.odi(gender=odi_gender)
            logger.info(f"ODI mode ({odi_gender}): {total_overs} overs, par={self.format_config.par_score:.1f}")
        else:
            self.format_config = FormatConfig.from_league(league) if league else FormatConfig.t20()

        # MC calibrator for reduced-over mode (loaded lazily)
        self._mc_calibrator = None
        # Optional richer debug output (defaults to sibling livematch.json if output_json is set)
        if live_match_json is None and output_json:
            try:
                live_match_json = self._build_live_match_json_path(output_json)
            except Exception:
                live_match_json = None
        self.live_match_json = live_match_json
        self.browser = None
        # `async_playwright().start()` owns a separate driver process. Closing
        # Chromium alone does not guarantee that driver exits when a predictor
        # is retired by the dashboard scheduler, so retain it for shutdown.
        self._playwright = None
        self.page = None
        self.match_state = MatchState()
        self.last_ball_number = ""
        self._running = False
        self._first_prediction = True  # Debug flag for first prediction
        self._prediction_history = []  # Track predictions over time
        self.local_storage = {}  # CREX localStorage for resolving team/player codes
        self._poll_count = 0  # Used to trigger periodic localStorage refresh
        self._inn1_cached_stats = {}  # Cache inn1 stats (PP runs, death RR, wickets) at innings break
        # Some CREX pages expose only innings summaries after a restart. Keep
        # the best summary so carryover features do not silently use defaults.
        self._inn1_page_stats = {}
        self._inn1_stats_source = "default"
        self._prediction_guard = None
        self._crex_inn1_api_attempted = False
        self._venue_pitch_baselines = None  # Loaded lazily from v14 router artifacts
        
        # Persist history to separate file for Streamlit page refresh resilience
        if output_json:
            self._history_file = self._build_history_file_path(output_json)
            self._load_history()  # Load existing history on startup
        else:
            self._history_file = None
        
        # Try to load the prediction model
        self.model = None
        self._load_model()
        self.market_stack = None
        self.market_stack_model_dir = None
        self.last_market_stack = {
            "status": "unavailable",
            "reason": "IPL innings-2 market stack candidate not loaded.",
        }
        self._last_market_update_at = None
        self._last_market_age_seconds = None
        self._last_market_api_fetch_at = None
        self._last_bowler_api_fetch_at = None
        self._load_market_stack_candidate()
        self._load_candidate_model()

        # ODM (Odds Direction Model) advisory
        from bbl_pipeline.inference.odds_direction_model import OddsDirectionModel

        self.odm_model = OddsDirectionModel.load(self.odm_model_dir)
        self.last_odm_prediction = {
            "status": "unavailable",
            "reason": "ODM model not configured.",
        }
        if self.odm_model_dir:
            print(f"[INFO] ODM advisory model: {self.odm_model.status}")

        # Initialize match state logger if recording enabled
        self.match_state_logger = None
        if self.record_states:
            self._init_match_state_logger()

    def _normalize_team_key(self, team_name: str) -> str:
        """Normalize a team string for comparison across codes/full names."""
        return re.sub(r'[^A-Z0-9]', '', (team_name or '').upper())

    @staticmethod
    def _normalize_live_url(match_url: str) -> str:
        """Normalize CREX match URLs to the live match page."""
        url = (match_url or "").strip().rstrip("/")
        for suffix in ("/match-details", "/match-scorecard", "/scorecard", "/info"):
            if url.endswith(suffix):
                return url[:-len(suffix)]
        return url

    @staticmethod
    def _build_live_match_json_path(output_json: str) -> str:
        """Build a per-feed debug JSON path so multiple predictors don't collide."""
        output_path = Path(output_json)
        return str(output_path.with_name(f"{output_path.stem}_livematch.json"))

    @staticmethod
    def _build_history_file_path(output_json: str) -> str:
        """Build a per-feed history JSON path so multiple predictors don't collide."""
        output_path = Path(output_json)
        return str(output_path.with_name(f"{output_path.stem}_history.json"))

    @staticmethod
    def _clean_team_text(team_name: str) -> str:
        """Trim CREX section labels from team-like text snippets."""
        candidate = re.sub(r'\s+', ' ', (team_name or '').strip()).strip(' -|,')
        candidate = re.sub(
            r'\s+(?:neither|both|without|with|despite|after|before|as|while|when)\b.*$',
            '',
            candidate,
            flags=re.IGNORECASE,
        )
        candidate = re.sub(
            r'\s+(?:in\s+Points\s+Table|Points\s+Table|Team\s+Form|Match\s+Info|Live|Scorecard|Commentary)\b.*$',
            '',
            candidate,
            flags=re.IGNORECASE,
        )
        candidate = re.sub(r'\s+\d+(?:st|nd|rd|th)[-\s]*Match\b.*$', '', candidate, flags=re.IGNORECASE)
        return candidate.strip(' -|,')

    @staticmethod
    def _clean_venue_text(venue_name: str) -> str:
        """Trim broadcast/page chrome accidentally captured after a venue name."""
        candidate = re.sub(r'\s+', ' ', (venue_name or '').strip()).strip(' -|,')
        candidate = re.sub(
            r'\s+(?:Star\s+Sports|JioHotstar|Sony\s+Sports|Willow\s+TV|Sky\s+Sports|FanCode|'
            r'Team\s+Form|Match\s+Info|Live|Scorecard|Commentary)\b.*$',
            '',
            candidate,
            flags=re.IGNORECASE,
        )
        candidate = re.sub(
            r'\s+\b(?:MI|CSK|RCB|KKR|SRH|DC|PBKS|RR|GT|LSG)\b.*$',
            '',
            candidate,
        )
        return candidate.rstrip(', ')

    @staticmethod
    def _looks_like_valid_team_name(team_name: str) -> bool:
        """Reject obvious article/preview snippets that are not team names."""
        candidate = re.sub(r'\s+', ' ', (team_name or '').strip())
        if not candidate:
            return False
        lower = candidate.lower()
        bad_fragments = (
            ' neither ', ' nor ', ' part of ', ' star sports', 'jiohotstar',
            ' points table', ' team form', ' match info', ' scorecard',
            ' commentary', ' live forecast',
        )
        padded = f" {lower} "
        if any(fragment in padded for fragment in bad_fragments):
            return False
        if len(candidate) > 45:
            return False
        if len(candidate.split()) > 5:
            return False
        return True

    def _known_team_codes(self) -> set[str]:
        """Return normalized team codes that may appear in CREX URL slugs."""
        codes = {
            'mi', 'csk', 'rcb', 'kkr', 'srh', 'dc', 'pbks', 'pk', 'rr', 'gt', 'lsg',
            'ind', 'aus', 'eng', 'nz', 'wi', 'sa', 'pak', 'sl', 'ban', 'afg', 'ck', 'jk', 'nep-a',
        }
        try:
            from bbl_pipeline.features.store import InMemoryFeatureStore

            for mapping_name in (
                'TEAM_ABBREVIATIONS_IPL',
                'TEAM_ABBREVIATIONS_PSL',
                'TEAM_ABBREVIATIONS_T20I',
                'TEAM_ABBREVIATIONS',
            ):
                mapping = getattr(InMemoryFeatureStore, mapping_name, {})
                codes.update(str(code).lower() for code in mapping)
        except Exception:
            pass
        return {code.replace('_', '-').lower() for code in codes if code}

    def _match_known_code_suffix(self, text: str) -> str:
        normalized = (text or '').strip('-/').lower()
        for code in sorted(self._known_team_codes(), key=len, reverse=True):
            if normalized == f'{code}-w' or normalized.endswith(f'-{code}-w'):
                return f'{code.upper()}-W'
            if normalized == code or normalized.endswith(f'-{code}'):
                return code.upper()
        parts = [part for part in normalized.split('-') if part]
        return parts[-1].upper() if parts else ''

    def _match_known_code_prefix(self, text: str) -> str:
        normalized = (text or '').strip('-/').lower()
        for code in sorted(self._known_team_codes(), key=len, reverse=True):
            if normalized == f'{code}-w' or normalized.startswith(f'{code}-w-'):
                return f'{code.upper()}-W'
            if normalized == code or normalized.startswith(f'{code}-'):
                return code.upper()
        parts = [part for part in normalized.split('-') if part]
        return parts[0].upper() if parts else ''

    def _extract_teams_from_url(self) -> Optional[tuple[str, str]]:
        """Extract teams from CREX URL slugs like csk-vs-mi-33rd-match..."""
        hinted_team1 = getattr(self, '_team1_name_hint', '')
        hinted_team2 = getattr(self, '_team2_name_hint', '')
        if (
            self._looks_like_valid_team_name(hinted_team1)
            and self._looks_like_valid_team_name(hinted_team2)
            and self._normalize_team_key(hinted_team1) != self._normalize_team_key(hinted_team2)
        ):
            return hinted_team1, hinted_team2

        for url in (self.match_url, self.original_match_url):
            if not url:
                continue
            match = re.search(r'/([^/?#]*?-vs-[^/?#]*)', url, re.IGNORECASE)
            if not match:
                continue
            slug = match.group(1).strip('/').lower()
            if '-vs-' not in slug:
                continue
            left, right = slug.split('-vs-', 1)
            left_code = self._match_known_code_suffix(left)
            right_code = self._match_known_code_prefix(right)
            team1 = self._resolve_team_name(left_code)
            team2 = self._resolve_team_name(right_code)
            if (
                team1
                and team2
                and self._looks_like_valid_team_name(team1)
                and self._looks_like_valid_team_name(team2)
                and self._normalize_team_key(team1) != self._normalize_team_key(team2)
            ):
                return team1, team2
        return None

    def _repair_match_teams_from_url(self) -> None:
        """Use URL teams to replace invalid or article-snippet team names."""
        teams = self._extract_teams_from_url()
        if not teams:
            return
        team1, team2 = teams
        self._team1 = team1
        self._team2 = team2

        batting = self.match_state.batting_team
        bowling = self.match_state.bowling_team
        batting_key = self._normalize_team_key(batting)
        team1_key = self._normalize_team_key(team1)
        team2_key = self._normalize_team_key(team2)

        if not self._looks_like_valid_team_name(batting):
            self.match_state.batting_team = team1
            batting_key = team1_key

        # A valid-looking pair can still come from an unrelated article or
        # scorecard embedded on the target page.  When both URL teams resolve,
        # they are the match identity and must win over that snippet.
        if batting_key not in {team1_key, team2_key}:
            self.match_state.batting_team = team1
            batting_key = team1_key

        # Once the provider pair is known, force a consistent two-team state.
        # A globally resolved short code is not sufficient because codes such
        # as DG are reused across competitions (Dublin Guardians vs Dhaka
        # Gladiators).  The current batting side determines the other side.
        if batting_key == team1_key:
            self.match_state.bowling_team = team2
        elif batting_key == team2_key:
            # A live scorecard may expose the first team by its full display
            # name while the URL only has its short code (for example HYK).
            # Preserve that already-opposite, valid display name; the
            # provider pair still remains the source of truth for identity.
            if not self._looks_like_valid_team_name(bowling) or self._normalize_team_key(bowling) == batting_key:
                self.match_state.bowling_team = team1
        else:
            self.match_state.batting_team = team1
            self.match_state.bowling_team = team2

    def _resolve_team_name(self, team_name: str) -> str:
        """Resolve CREX team codes into displayable team names when possible."""
        candidate = self._clean_team_text(team_name)
        if not candidate:
            return ""

        storage_name = self.local_storage.get(f"t_{candidate.upper()}_name")
        if isinstance(storage_name, str) and storage_name.strip():
            return storage_name.strip()

        league = (self.league or '').lower()
        code = candidate.upper()
        base_code = code[:-2] if code.endswith('-W') else code
        if code.endswith('W') and len(code) >= 3 and not code.endswith('-W'):
            base_code = code[:-1]

        static_league_maps = {
            'ipl': {
                'MI': 'Mumbai Indians',
                'CSK': 'Chennai Super Kings',
                'RCB': 'Royal Challengers Bengaluru',
                'KKR': 'Kolkata Knight Riders',
                'SRH': 'Sunrisers Hyderabad',
                'DC': 'Delhi Capitals',
                'PBKS': 'Punjab Kings',
                'PK': 'Punjab Kings',
                'RR': 'Rajasthan Royals',
                'GT': 'Gujarat Titans',
                'LSG': 'Lucknow Super Giants',
            },
            't20_all': {
                # Lanka Premier League abbreviations are not present in the
                # historical feature-store maps.  Without these, CREX page
                # body snippets can replace the live CK/Jaffna fixture with
                # an unrelated domestic game mentioned lower on the page.
                'CK': 'Colombo Kaps',
                'JK': 'Jaffna Kings',
                # European T20 Premier League codes. DG is also used by the
                # historical Dhaka Gladiators map, so competition-local
                # resolution is mandatory here.
                'DG': 'Dublin Guardians',
                'BW': 'Belfast Wolves',
                'ECR': 'Edinburgh Castle Rockers',
                'RD': 'Rotterdam Dockers',
                'GC': 'Glasgow Cosmic',
                'AF': 'Amsterdam Flames',
            },
        }
        league_map = static_league_maps.get(league)
        if league_map:
            direct_match = league_map.get(code) or league_map.get(base_code)
            if direct_match:
                return direct_match

        try:
            from bbl_pipeline.features.store import InMemoryFeatureStore

            resolved = None
            feature_store = getattr(getattr(self, 'predictor', None), 'feature_store', None)
            if feature_store and hasattr(feature_store, '_resolve_team_abbrev'):
                resolved_candidate = feature_store._resolve_team_abbrev(candidate)
                if isinstance(resolved_candidate, str) and resolved_candidate.strip():
                    resolved_candidate = resolved_candidate.strip()
                    # Some feature-store contexts return the original short code unchanged.
                    if (
                        self._normalize_team_key(resolved_candidate) != self._normalize_team_key(candidate)
                        or " " in resolved_candidate
                        or len(resolved_candidate) > len(candidate)
                    ):
                        resolved = resolved_candidate
            if not resolved:
                if league in ('ipl', 'indian_premier_league'):
                    resolved = (
                        InMemoryFeatureStore.TEAM_ABBREVIATIONS_IPL.get(code)
                        or InMemoryFeatureStore.TEAM_ABBREVIATIONS_IPL.get(base_code)
                    )
                elif league in ('psl', 'pakistan_super_league'):
                    resolved = (
                        InMemoryFeatureStore.TEAM_ABBREVIATIONS_PSL.get(code)
                        or InMemoryFeatureStore.TEAM_ABBREVIATIONS_PSL.get(base_code)
                    )
                elif league in ('t20i', 't20i_female', 't20_international', 't20_international_female'):
                    resolved = (
                        InMemoryFeatureStore.TEAM_ABBREVIATIONS_T20I.get(base_code)
                        or InMemoryFeatureStore.TEAM_ABBREVIATIONS_T20I.get(code)
                    )
                else:
                    resolved = (
                        InMemoryFeatureStore.TEAM_ABBREVIATIONS.get(base_code)
                        or InMemoryFeatureStore.TEAM_ABBREVIATIONS.get(code)
                    )
            if isinstance(resolved, str) and resolved.strip():
                return resolved.strip()
        except Exception:
            pass

        return candidate

    def _extract_vs_teams(self, text: str) -> Optional[tuple[str, str]]:
        """Extract and resolve both teams from CREX text/title content."""
        if not text:
            return None

        code_match = re.search(
            r"\b([A-Z][A-Z0-9]{1,5}(?:-[A-Z])?)\s+vs\s+([A-Z][A-Z0-9]{1,5}(?:-[A-Z])?)\b",
            text,
        )
        if code_match:
            team1 = self._resolve_team_name(code_match.group(1))
            team2 = self._resolve_team_name(code_match.group(2))
            if (
                team1
                and team2
                and self._looks_like_valid_team_name(team1)
                and self._looks_like_valid_team_name(team2)
                and self._normalize_team_key(team1) != self._normalize_team_key(team2)
            ):
                return team1, team2

        patterns = [
            r"([A-Za-z0-9][A-Za-z0-9&.'\- ]{1,50}?)\s+vs\s+([A-Za-z0-9][A-Za-z0-9&.'\- ]{1,60}?)(?:\s+\d+(?:st|nd|rd|th)[-\s]*Match\b|\s+\|\s+|\s+Team Form\b|\s+Match Info\b|\s+Live\b|\s+Scorecard\b|\s+Commentary\b|$)",
            r"([A-Za-z0-9][A-Za-z0-9&.'\- ]{1,50}?)\s+vs\s+([A-Za-z0-9][A-Za-z0-9&.'\- ]{1,60}?)(?:\n|$)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if not match:
                continue
            team1 = self._resolve_team_name(match.group(1))
            team2 = self._resolve_team_name(match.group(2))
            if (
                team1
                and team2
                and self._looks_like_valid_team_name(team1)
                and self._looks_like_valid_team_name(team2)
                and self._normalize_team_key(team1) != self._normalize_team_key(team2)
            ):
                return team1, team2
        return None

    def _resolve_scorecard_team_from_provider_pair(self, raw_team: str) -> Optional[str]:
        """Map a scorecard's current-team label onto the provider pair.

        CREX short codes are not globally unique.  A local-storage or feature
        store lookup can therefore resolve a scorecard label such as ``RD`` to
        an unrelated team's display name.  When the scheduler supplied the
        provider-authoritative pair, use the raw scorecard label plus the
        canonical URL's two code positions to determine which side is batting
        before consulting any global fallback map.
        """
        hinted_team1 = getattr(self, '_team1_name_hint', '')
        hinted_team2 = getattr(self, '_team2_name_hint', '')
        if not (
            self._looks_like_valid_team_name(hinted_team1)
            and self._looks_like_valid_team_name(hinted_team2)
            and self._normalize_team_key(hinted_team1) != self._normalize_team_key(hinted_team2)
        ):
            return None

        raw_key = self._normalize_team_key(self._clean_team_text(raw_team))
        if not raw_key:
            return None
        team1_key = self._normalize_team_key(hinted_team1)
        team2_key = self._normalize_team_key(hinted_team2)
        if raw_key == team1_key:
            return hinted_team1
        if raw_key == team2_key:
            return hinted_team2

        for url in (self.match_url, self.original_match_url):
            if not url:
                continue
            match = re.search(r'/([^/?#]*?-vs-[^/?#]*)', url, re.IGNORECASE)
            if not match:
                continue
            slug = match.group(1).strip('/').lower()
            if '-vs-' not in slug:
                continue
            left, right = slug.split('-vs-', 1)
            left_code = self._match_known_code_suffix(left)
            right_code = self._match_known_code_prefix(right)
            if raw_key == self._normalize_team_key(left_code):
                return hinted_team1
            if raw_key == self._normalize_team_key(right_code):
                return hinted_team2
        return None

    @staticmethod
    def _extract_batter_pair(text: str) -> Optional[tuple[str, int, int, str, int, int]]:
        """Extract two live batters from CREX title/body text.

        CREX layouts vary; this accepts initials, dots, apostrophes, hyphens,
        and optional not-out stars in strings like:
        "S Dube 43*(24), R Jadeja 6(2)".
        """
        if not text:
            return None
        player = r"([A-Za-z][A-Za-z.'\- ]{0,40}?)\s+(\d+)\*?\s*\((\d+)\)"
        pair_match = re.search(
            rf"{player}\s*,\s*{player}",
            text,
            re.IGNORECASE,
        )
        if not pair_match:
            return None
        return (
            pair_match.group(1).strip(),
            int(pair_match.group(2)),
            int(pair_match.group(3)),
            pair_match.group(4).strip(),
            int(pair_match.group(5)),
            int(pair_match.group(6)),
        )

    def _apply_batter_pair(self, pair: tuple[str, int, int, str, int, int] | None) -> None:
        if not pair:
            return
        (
            self.match_state.batsman1_name,
            self.match_state.batsman1_runs,
            self.match_state.batsman1_balls,
            self.match_state.batsman2_name,
            self.match_state.batsman2_runs,
            self.match_state.batsman2_balls,
        ) = pair

    @staticmethod
    def _second_innings_is_supported(
        current_team: str,
        current_runs: int,
        first_innings_team: str,
        first_innings_runs: int,
        has_needs_runs: bool = False,
        has_required_run_rate: bool = False,
    ) -> bool:
        """Require evidence that the scorecard has moved to the chase.

        CREX pages can show the completed-innings summary as ``vs TEAM
        205-10`` while the first innings is still on the live scorecard.  The
        old ``first_innings_match`` check treated that summary alone as an
        innings change and emitted rows with the first-innings team in the
        batting slot.  Explicit chase text is authoritative; otherwise the
        current score must belong to the other provider team and still be
        below the completed first-innings score.
        """
        if has_needs_runs or has_required_run_rate:
            return True
        if not first_innings_team or first_innings_runs < 0:
            return False

        normalize = lambda value: re.sub(r"[^A-Z0-9]", "", str(value or "").upper())
        current_key = normalize(current_team)
        first_key = normalize(first_innings_team)
        if current_key and first_key and current_key == first_key:
            return False
        return int(current_runs or 0) < int(first_innings_runs)

    @staticmethod
    def _current_bowler_is_valid(name: str, wickets: int, runs: int, overs: float) -> bool:
        """Reject score-summary text accidentally captured as a bowler.

        A hydrated CREX page may expose the completed first-innings summary
        through the same broad CSS selector used by older layouts.  Values
        such as ``st innings over 10-205 (19.3)`` are not a player/figure
        record and must never reach inference or the evidence trail.
        """
        clean_name = str(name or "").strip()
        if not clean_name or re.search(r"\b(?:innings?|over|score|target|need|rate)\b", clean_name, re.IGNORECASE):
            return False
        try:
            wickets_value = int(wickets)
            runs_value = int(runs)
            overs_value = float(overs)
        except (TypeError, ValueError):
            return False
        return (
            0 <= wickets_value <= 10
            and 0 <= runs_value <= 1000
            and 0 <= overs_value <= 50
        )

    def _clear_invalid_current_bowler(self) -> None:
        if self._current_bowler_is_valid(
            self.match_state.bowler1_name,
            self.match_state.bowler1_wickets,
            self.match_state.bowler1_runs,
            self.match_state.bowler1_overs,
        ):
            return
        self.match_state.bowler1_name = ""
        self.match_state.bowler1_overs = 0.0
        self.match_state.bowler1_runs = 0
        self.match_state.bowler1_wickets = 0
    
    def _init_match_state_logger(self):
        """Initialize match state logger if recording is enabled."""
        try:
            from pathlib import Path
            from bbl_pipeline.inference.match_state_logger import MatchStateLogger
            
            # Use the final non-empty provider URL segment.  The old ``[-2]``
            # expression only worked for a trailing slash and otherwise
            # produced ``cricket-live-score`` for every match in that feed.
            url_parts = [part for part in self.match_url.split("/") if part]
            match_id = url_parts[-1].split("?", 1)[0].split("#", 1)[0] if url_parts else "unknown_match"
            if not match_id or match_id.lower() in {"live", "scoreboard", "info"}:
                match_id = "unknown_match"
            
            # Determine states directory
            if self.states_dir:
                states_dir = Path(self.states_dir)
            elif self.league:
                states_dir = Path(f"data/match_states/{self.league}")
            else:
                states_dir = Path("data/match_states/unknown")
            
            # Extract version strings
            model_version = Path(self.model_dir).name if self.model_dir else "unknown_model"
            feature_store_version = Path(self.feature_store_dir).name if self.feature_store_dir else "unknown_store"
            
            # Create logger
            self.match_state_logger = MatchStateLogger(
                match_id=match_id,
                league=self.league or "unknown",
                states_dir=states_dir,
                model_version=model_version,
                feature_store_version=feature_store_version,
                match_url=self.match_url,
            )
            print(f"[RECORD] Match state recording enabled -> {states_dir}/{match_id}.parquet")
        except Exception as e:
            print(f"[WARN] Could not initialize match state logger: {e}")
            self.match_state_logger = None

    def _load_candidate_model(self) -> None:
        """Load an optional candidate model for shadow scoring only."""
        if not self.candidate_model_dir or self.mc_only:
            return
        try:
            candidate_dir = Path(self.candidate_model_dir)
            manifest_path = candidate_dir / "candidate_manifest.json"
            if manifest_path.exists():
                from bbl_pipeline.analysis.candidate_manifest import validate_candidate_manifest

                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                validated = validate_candidate_manifest(manifest, candidate_dir)
                self.candidate_model_version = validated["candidate_id"]
                self.candidate_artifact_sha256 = validated["model_artifact_sha256"]
                self.candidate_feature_order_sha256 = validated["feature_order_sha256"]
                self.candidate_source_revision = validated["source_revision"]

            from bbl_pipeline.inference.predictor import Predictor

            self.candidate_predictor = Predictor.load(
                self.candidate_model_dir,
                self.feature_store_dir,
                league=self.league,
            )
            # The candidate must see exactly the same format configuration as
            # the incumbent process, including reduced/ODI overrides.
            self.candidate_predictor.format_config = self.format_config
            self.candidate_predictor.feature_mapper.format_config = self.format_config
            self.candidate_predictor.resource_calculator.config = self.format_config
            self.candidate_model_version = Path(self.candidate_model_dir).name
            print(f"[SHADOW] Candidate model loaded: {self.candidate_model_dir}")
        except Exception as e:
            logger.warning(f"Candidate model unavailable; continuing incumbent-only: {e}")
            self.candidate_predictor = None

    def _run_candidate_shadow(self, pred_state: Any, ball_history: list) -> Optional[float]:
        """Score the same live state with the candidate without changing output."""
        if self.candidate_predictor is None:
            return None
        try:
            probability = self.candidate_predictor.predict(
                pred_state,
                debug=False,
                ball_history=list(ball_history or []),
            )
            probability = float(probability)
            if 0.0 <= probability <= 1.0:
                return probability
        except Exception as e:
            logger.warning(f"Candidate shadow prediction failed: {e}")
        return None
    
    def _load_model(self):
        """Load the trained prediction model."""
        # Skip model loading entirely in MC-only mode
        if self.mc_only:
            print("[INFO] MC-only mode — skipping ML model loading")
            self.predictor = None
            return
        try:
            from bbl_pipeline.inference.predictor import Predictor

            # Detect routing config — if present, load inn1 model from routing_config.inn1_model_dir
            routing_cfg = None
            routing_config_path = Path(self.model_dir) / "routing_config.json"
            if routing_config_path.exists():
                import json as _json
                with open(routing_config_path) as _rf:
                    routing_cfg = _json.load(_rf)

            if routing_cfg and routing_cfg.get("type") == "inn2_phase_router":
                inn1_dir = routing_cfg.get("inn1_model_dir", self.model_dir)
                # Paths in routing_config.json are project-root-relative (same cwd as the process)
                inn1_dir_resolved = Path(inn1_dir)
                print(f"[INFO] IPL innings router: loading inn1 model from {inn1_dir_resolved}")
                self.predictor = Predictor.load(
                    inn1_dir_resolved, self.feature_store_dir, league=self.league
                )
            else:
                self.predictor = Predictor.load(self.model_dir, self.feature_store_dir, league=self.league)

            self.model = self.predictor.model
            print(f"[OK] Model loaded from {self.model_dir}")
            if self.feature_store_dir:
                print(f"[INFO] Feature store: {self.feature_store_dir}")
            # Live inference may use the current CREX match-info venue prior;
            # keep the class default disabled so training-parity paths remain
            # unchanged.
            if getattr(self.predictor, 'feature_store', None) is not None:
                self.predictor.feature_store.USE_VENUE_SITUATION_OVERRIDES = True
            if self.league:
                print(f"[INFO] League calibrator: {self.league}")

            # Attach inn2 phase router if routing config present
            if routing_cfg and routing_cfg.get("type") == "inn2_phase_router":
                try:
                    from bbl_pipeline.inference.inn2_phase_router import Inn2PhaseRouter
                    phase_dir = routing_cfg.get("inn2_phase_model_dir", "models/ipl_inn2_v1")
                    # Paths are project-root-relative
                    self.predictor.inn2_router = Inn2PhaseRouter.load(Path(phase_dir))
                    print(f"[OK] Inn2PhaseRouter loaded from {phase_dir}")
                    post_cfg = routing_cfg.get("post_model_calibration", {})
                    if post_cfg.get("enabled"):
                        try:
                            from bbl_pipeline.inference.post_model_calibration_router import (
                                PostModelCalibrationRouter,
                            )

                            artifact_path = Path(post_cfg.get("artifact", "post_model_calibration_router.pkl"))
                            if not artifact_path.is_absolute():
                                artifact_path = Path(phase_dir) / artifact_path
                            self.predictor.post_model_calibration_router = PostModelCalibrationRouter.load(artifact_path)
                            print(f"[OK] PostModelCalibrationRouter loaded from {artifact_path}")
                        except Exception as _pe:
                            print(f"[WARN] Could not load PostModelCalibrationRouter: {_pe} — using raw router output")
                except Exception as _re:
                    print(f"[WARN] Could not load Inn2PhaseRouter: {_re} — v7 fallback for all innings")
        except Exception as e:
            print(f"[WARN] Could not load model: {e}")
            print("   Will run in scraper-only mode (no predictions)")
            self.predictor = None

    def _load_market_stack_candidate(self):
        """Load the inactive IPL innings-2 market-stack candidate for dry-run output."""
        league_code = (self.league or "").lower()
        model_name = Path(self.model_dir).name.lower() if self.model_dir else ""
        if league_code not in {"ipl", "indian_premier_league"} and "ipl" not in model_name:
            return

        if self.market_stack_model_dir_override:
            candidate_dir = Path(self.market_stack_model_dir_override)
        else:
            candidate_dir = Path(__file__).resolve().parents[3] / "models" / "ipl_v7_inn2_market_stack_candidate"
        stack_path = candidate_dir / "inn2_market_stack.joblib"
        if not stack_path.exists():
            self.last_market_stack = {
                "status": "unavailable",
                "reason": f"Market-stack candidate not found at {stack_path}",
            }
            return

        try:
            import joblib

            artifact = joblib.load(stack_path)
            model = artifact.get("model") if isinstance(artifact, dict) else artifact
            input_features = artifact.get("input_features", []) if isinstance(artifact, dict) else []
            if model is None or not hasattr(model, "predict_proba"):
                raise ValueError("market stack artifact does not contain a predict_proba model")
            if not input_features:
                input_features = ["logit_iso_p_inn1", "logit_market_p_inn1"]

            self.market_stack = {
                "model": model,
                "input_features": list(input_features),
                "probability_space": artifact.get("probability_space", "p_innings1_wins") if isinstance(artifact, dict) else "p_innings1_wins",
                "applies_to": artifact.get("applies_to", "innings_2_only") if isinstance(artifact, dict) else "innings_2_only",
            }
            self.market_stack_model_dir = str(candidate_dir)
            self.last_market_stack = {
                "status": "loaded",
                "model_dir": self.market_stack_model_dir,
                "is_dry_run": True,
                "used_for_primary": False,
            }
            print(f"[INFO] Loaded IPL inn2 market-stack candidate (dry-run): {candidate_dir}")
        except Exception as e:
            self.market_stack = None
            self.last_market_stack = {
                "status": "error",
                "reason": f"Failed to load market-stack candidate: {e}",
            }

    @staticmethod
    def _clip_probability(value: float, eps: float = 1e-3) -> float:
        return max(eps, min(1.0 - eps, float(value)))

    @classmethod
    def _logit_probability(cls, value: float) -> float:
        import math

        prob = cls._clip_probability(value)
        return math.log(prob / (1.0 - prob))

    def _market_age_seconds(self) -> Optional[float]:
        if self._last_market_update_at is None:
            return None
        return max(0.0, (datetime.now() - self._last_market_update_at).total_seconds())

    def _get_market_batting_probability(self) -> Optional[float]:
        """Return market-implied P(current batting team wins), if odds can be mapped."""
        state = self.match_state
        if not state.market_fav_prob or not state.market_fav_team:
            return None

        if self.match_state_logger:
            market_batting_prob, _ = self.match_state_logger._map_market_probs(
                state.market_fav_team,
                state.market_fav_prob,
                state.batting_team,
                state.bowling_team,
            )
            return market_batting_prob

        fav_key = self._normalize_team_key(state.market_fav_team)
        batting_key = self._normalize_team_key(state.batting_team)
        bowling_key = self._normalize_team_key(state.bowling_team)
        if fav_key == batting_key:
            return float(state.market_fav_prob)
        if fav_key == bowling_key:
            return 1.0 - float(state.market_fav_prob)
        return None

    def _compute_market_stack_overlay(
        self,
        win_prob: float,
        market_batting_prob: Optional[float],
    ) -> Dict[str, Any]:
        """Compute dry-run innings-2 stack probability without changing primary output."""
        state = self.match_state
        terminal_clamp = getattr(
            self,
            "_last_terminal_clamp",
            getattr(getattr(self, "predictor", None), "last_terminal_clamp", None),
        )

        if not self.market_stack:
            return dict(self.last_market_stack)
        if not state.is_second_innings:
            return {
                "status": "not_applicable",
                "reason": "Market stack applies to innings 2 only.",
                "is_dry_run": True,
                "used_for_primary": False,
            }
        if market_batting_prob is None:
            return {
                "status": "unavailable",
                "reason": "Market probability could not be mapped to batting/bowling team.",
                "is_dry_run": True,
                "used_for_primary": False,
            }

        try:
            import pandas as pd

            base_bat_prob = self._clip_probability(win_prob)
            market_bat_prob = self._clip_probability(market_batting_prob)
            base_inn1_prob = self._clip_probability(1.0 - base_bat_prob)
            market_inn1_prob = self._clip_probability(1.0 - market_bat_prob)

            row = {
                "logit_iso_p_inn1": self._logit_probability(base_inn1_prob),
                "logit_market_p_inn1": self._logit_probability(market_inn1_prob),
            }
            input_features = self.market_stack["input_features"]
            X = pd.DataFrame([{feature: row[feature] for feature in input_features}])
            stack_inn1_prob = float(self.market_stack["model"].predict_proba(X)[0, 1])
            stack_inn1_prob = self._clip_probability(stack_inn1_prob)
            stack_bat_prob = 1.0 - stack_inn1_prob

            result = {
                "status": "ready",
                "model_dir": self.market_stack_model_dir,
                "applies_to": self.market_stack.get("applies_to", "innings_2_only"),
                "probability_space": self.market_stack.get("probability_space", "p_innings1_wins"),
                "is_dry_run": True,
                "used_for_primary": False,
                "market_age_seconds": self._market_age_seconds(),
                "base_bat_win_prob": float(base_bat_prob),
                "base_inn1_win_prob": float(base_inn1_prob),
                "market_bat_win_prob": float(market_bat_prob),
                "market_inn1_win_prob": float(market_inn1_prob),
                "stack_bat_win_prob": float(stack_bat_prob),
                "stack_inn1_win_prob": float(stack_inn1_prob),
                "delta_bat_vs_base": float(stack_bat_prob - base_bat_prob),
                "delta_inn1_vs_base": float(stack_inn1_prob - base_inn1_prob),
                "terminal_clamp": terminal_clamp,
            }
            self.last_market_stack = result
            return result
        except Exception as e:
            result = {
                "status": "error",
                "reason": str(e),
                "is_dry_run": True,
                "used_for_primary": False,
                "terminal_clamp": terminal_clamp,
            }
            self.last_market_stack = result
            return result
     
    def _load_history(self):
        """Load prediction history from file for persistence across restarts."""
        if not self._history_file:
            return
        try:
            history_path = Path(self._history_file)
            if history_path.exists():
                with open(history_path, 'r') as f:
                    data = json.load(f)
                    # Check if history belongs to current match
                    saved_url = data.get("match_url")
                    if saved_url and saved_url != self.match_url:
                        print(f"[NEW] New match detected (URL mismatch). Clearing history.")
                        self._prediction_history = []
                        return
                        
                    self._prediction_history = data.get("history", [])
                    print(f"[HIST] Loaded {len(self._prediction_history)} history points from {self._history_file}")
        except Exception as e:
            logger.warning(f"Could not load history: {e}")
            self._prediction_history = []
    
    def _save_history(self):
        """Save prediction history to file for persistence."""
        if not self._history_file:
            return
        try:
            history_path = Path(self._history_file)
            tmp_path = history_path.with_suffix('.tmp')
            with open(tmp_path, 'w') as f:
                json.dump({
                    "match_url": self.match_url,
                    "history": self._prediction_history
                }, f)
            tmp_path.replace(history_path)
        except Exception as e:
            logger.warning(f"Could not save history: {e}")
    
    def _balls_bowled_from_overs(self, overs: float | int | None) -> int:
        """Convert cricket over notation into the active format's legal balls."""
        try:
            value = float(overs or 0)
        except (TypeError, ValueError):
            return 0
        over_number = max(0, int(value))
        ball_number = max(0, int(round((value - over_number) * 10)))
        balls_per_over = int(self.format_config.balls_per_over or 6)
        return min(
            int(self.format_config.total_balls),
            over_number * balls_per_over + min(balls_per_over, ball_number),
        )

    def _run_monte_carlo_simulation(self, model_prob: Optional[float] = None, use_ml_model: bool = False) -> Optional[Dict[str, Any]]:
        """
        Run Monte Carlo simulation for uncertainty quantification.
        
        Args:
            model_prob: League-calibrated model probability from predictor.predict().
                       If provided, this is used for edge calculation in betting decisions
                       (more accurate than simulation mean which uses resource_win_prob).
            use_ml_model: If True, use ML model for terminal state evaluation (slower but
                         more accurate ~400-800ms). If False, use resource_win_prob heuristic
                         (faster ~60ms but less accurate).
        
        Returns dict with simulation results or None if unavailable.
        """
        # The shared simulation engine currently models six-ball innings and
        # rejects Hundred's 100-ball format. Keep the trained Hundred model
        # probability available while the dedicated 100-ball simulator is
        # still being completed.
        if self.format_config.format_name == "hundred":
            return None
        if not SIMULATION_AVAILABLE:
            return None
        
        try:
            state = self.match_state
            
            # Calculate balls remaining
            overs_float = state.overs
            balls_bowled = self._balls_bowled_from_overs(overs_float)
            balls_remaining = self.format_config.total_balls - balls_bowled
            
            if balls_remaining <= 0:
                return None
            
            # Use self.league if provided, otherwise detect from format/model_dir
            league = self.league  # Prefer explicitly set league
            if not league:
                # Auto-detect ODI from format config
                effective_overs = self._effective_total_overs or self.format_config.total_overs
                if effective_overs >= 40:
                    league = "odi"
                else:
                    # Fallback: detect from model_dir path
                    model_dir_lower = self.model_dir.lower() if self.model_dir else ""
                    if "t20_international" in model_dir_lower or "t20i" in model_dir_lower:
                        league = "t20i"
                    elif "sa20" in model_dir_lower or "sat_" in model_dir_lower:
                        league = "sa20"
                    elif "ilt20" in model_dir_lower or "ilt_" in model_dir_lower:
                        league = "ilt20"
                    elif "wpl" in model_dir_lower:
                        league = "wpl"
                    elif "ssm" in model_dir_lower:
                        league = "ssm"
                    elif "bpl" in model_dir_lower:
                        league = "bpl"
                    elif "odm_male" in model_dir_lower:
                        league = "odm_male"
                    elif "odm_female" in model_dir_lower:
                        league = "odm_female"
                    elif "odi" in model_dir_lower:
                        league = "odi"
                    elif "female" in model_dir_lower:
                        league = None  # Global female model
                    else:
                        league = "bbl"  # Default for T20
            
            # Create simulation state
            # Get team stats from feature store for accurate Monte Carlo
            batting_team_wr = 0.5
            bowling_team_wr = 0.5
            batting_team_sit_wr = 0.5
            bowling_team_sit_wr = 0.5
            
            if self.predictor and hasattr(self.predictor, 'feature_store'):
                fs = self.predictor.feature_store
                bat_stats = fs.get_team_stats(state.batting_team)
                bowl_stats = fs.get_team_stats(state.bowling_team)
                if bat_stats:
                    batting_team_wr = bat_stats.get('win_rate', 0.5)
                    # Use appropriate situation rate based on innings
                    if state.is_second_innings:
                        batting_team_sit_wr = bat_stats.get('bowl_first_wr', batting_team_wr)  # They batted 2nd
                    else:
                        batting_team_sit_wr = bat_stats.get('bat_first_wr', batting_team_wr)
                if bowl_stats:
                    bowling_team_wr = bowl_stats.get('win_rate', 0.5)
                    if state.is_second_innings:
                        bowling_team_sit_wr = bowl_stats.get('bat_first_wr', bowling_team_wr)  # They batted 1st
                    else:
                        bowling_team_sit_wr = bowl_stats.get('bowl_first_wr', bowling_team_wr)
            
            sim_state = SimMatchState(
                innings=2 if state.is_second_innings else 1,
                score=state.total_runs,
                wickets_lost=state.wickets,
                balls_remaining=balls_remaining,
                target_runs=state.target if state.is_second_innings else None,
                batting_team=state.batting_team,
                bowling_team=state.bowling_team,
                league=league,
                venue=state.venue,
                total_balls=self.format_config.total_balls,
                batting_team_win_rate=batting_team_wr,
                bowling_team_win_rate=bowling_team_wr,
                batting_team_situation_wr=batting_team_sit_wr,
                bowling_team_situation_wr=bowling_team_sit_wr,
            )
            
            # Choose predictor for ML model mode
            predictor = self.predictor if use_ml_model else None
            
            # Resolve model_dir for MC calibrator loading.
            # For ODI mc-only mode, fall back to models/odi_mc_v1 if self.model_dir
            # doesn't contain MC calibrators (e.g. default models/champion_final).
            mc_model_dir = self.model_dir
            if league == "odi" or league == "odi_female" or (self._effective_total_overs or self.format_config.total_overs) >= 40:
                import os
                if not os.path.exists(os.path.join(self.model_dir, "mc_calibrators_innings_phase.pkl")):
                    # Try gender-specific fallback first, then generic ODI
                    is_female = league and "female" in league
                    fallback_candidates = (
                        ["models/odi_female_mc_v1", "models/odi_mc_v1"] if is_female
                        else ["models/odi_mc_v1"]
                    )
                    for odi_fallback in fallback_candidates:
                        if os.path.isdir(odi_fallback):
                            mc_model_dir = odi_fallback
                            logger.debug(f"Using ODI MC calibrator dir: {mc_model_dir}")
                            break
            
            # Run 1-ball simulation (fast)
            result_1ball = simulate(sim_state, horizon=1, n_simulations=1000, predictor=predictor, model_dir=mc_model_dir)
            
            # Run 6-ball (1 over) simulation
            result_6ball = simulate_one_over(sim_state, n_simulations=2000, predictor=predictor, model_dir=mc_model_dir)
            
            # Run 12-ball (2 over) simulation
            result_12ball = simulate_two_overs(sim_state, n_simulations=2000, predictor=predictor, model_dir=mc_model_dir)
            
            # Run 30-ball (5 over) simulation - useful for first innings uncertainty
            result_30ball = simulate_five_overs(sim_state, n_simulations=2000, predictor=predictor, model_dir=mc_model_dir)
            
            # Evaluate betting decision if market odds available
            # Uses league-calibrated model_prob for edge calculation (more accurate than simulation mean)
            betting_decision = None
            if state.market_back_odds:
                try:
                    odds = float(state.market_back_odds)
                    if odds > 1.0:
                        decision = evaluate_bet(
                            simulation_result=result_6ball,
                            market_odds=odds,
                            balls_remaining=balls_remaining,
                            model_prob=model_prob,  # League-calibrated probability for edge
                        )
                        betting_decision = {
                            "decision": decision.decision.value,
                            "edge": decision.edge,
                            "kelly_stake": decision.kelly_stake,
                            "confidence": decision.confidence,
                            "phase": decision.phase,
                            "rationale": decision.rationale,
                            "model_prob": decision.model_prob,  # Include in output
                            "simulation_mean": result_6ball.mean_prob,  # Also include simulation mean for comparison
                        }
                except (ValueError, TypeError):
                    pass
            
            return {
                "available": True,
                "league": league,
                "balls_remaining": balls_remaining,
                "use_ml_model": use_ml_model,  # Indicates whether ML model was used for terminal evaluation
                "simulation_1ball": {
                    "mean_prob": result_1ball.mean_prob,
                    "raw_mean": result_1ball.raw_mean,
                    "std_prob": result_1ball.std_prob,
                    "p5": result_1ball.p5,
                    "p95": result_1ball.p95,
                    "n_sims": result_1ball.n_sims,
                    "time_ms": result_1ball.time_taken_ms,
                },
                "simulation_6ball": {
                    "mean_prob": result_6ball.mean_prob,
                    "raw_mean": result_6ball.raw_mean,
                    "std_prob": result_6ball.std_prob,
                    "p5": result_6ball.p5,
                    "p95": result_6ball.p95,
                    "n_sims": result_6ball.n_sims,
                    "time_ms": result_6ball.time_taken_ms,
                },
                "simulation_12ball": {
                    "mean_prob": result_12ball.mean_prob,
                    "raw_mean": result_12ball.raw_mean,
                    "std_prob": result_12ball.std_prob,
                    "p5": result_12ball.p5,
                    "p95": result_12ball.p95,
                    "n_sims": result_12ball.n_sims,
                    "time_ms": result_12ball.time_taken_ms,
                },
                "simulation_30ball": {
                    "mean_prob": result_30ball.mean_prob,
                    "raw_mean": result_30ball.raw_mean,
                    "std_prob": result_30ball.std_prob,
                    "p5": result_30ball.p5,
                    "p95": result_30ball.p95,
                    "n_sims": result_30ball.n_sims,
                    "time_ms": result_30ball.time_taken_ms,
                },
                "betting_decision": betting_decision,
            }
            
        except Exception as e:
            logger.warning(f"Monte Carlo simulation failed: {e}")
            return {"available": False, "error": str(e)}

    def _get_info_url(self) -> str:
        """Convert live URL to info URL.
        
        CREX info page format: .../match-details
        Legacy format (some leagues): .../live → .../info
        """
        url = self._normalize_live_url(self.match_url).rstrip("/")
        if "/live" in url:
            return url.replace("/live", "/match-details")
        # Default: append /match-details
        return url + "/match-details"
    
    async def _extract_team_comparison(self, page_text: str, team1: str, team2: str):
        """
        Extract team comparison stats from CREX info page and inject into feature store.
        
        Example text pattern:
        Team Comparison (Last 10 matches)
        IND vs all teams NZ vs all teams
        10 Matches Played 8
        80% Win 60%
        165 Avg Score 148
        
        Note: The order of teams in the comparison table may differ from the match title!
        We need to extract team abbreviations from "XXX vs all teams" to match correctly.
        """
        try:
            import re
            
            # First, extract the team abbreviations from the comparison headers
            # Pattern: "XXX vs all teams YYY vs all teams"
            team_headers_pattern = r'([A-Z0-9\-]+)\s+vs\s+all\s+teams\s+([A-Z0-9\-]+)\s+vs\s+all\s+teams'
            team_headers_match = re.search(team_headers_pattern, page_text, re.IGNORECASE)
            
            if not team_headers_match:
                logger.warning("Could not find team comparison headers")
                return
                
            # These are the teams in the order they appear in the comparison table
            left_team = team_headers_match.group(1)
            right_team = team_headers_match.group(2)
            
            # Now extract the stats (these correspond to left and right columns)
            matches_pattern = r'(\d+)\s*Matches\s*Played\s*(\d+)'
            win_pattern = r'(\d+)%\s*Win\s*(\d+)%'
            avg_score_pattern = r'(\d+)\s*Avg\s*Score\s*(\d+)'
            
            matches_match = re.search(matches_pattern, page_text, re.IGNORECASE)
            win_match = re.search(win_pattern, page_text, re.IGNORECASE)
            avg_score_match = re.search(avg_score_pattern, page_text, re.IGNORECASE)
            
            if matches_match and win_match:
                left_matches = int(matches_match.group(1))
                right_matches = int(matches_match.group(2))
                left_win_pct = int(win_match.group(1)) / 100
                right_win_pct = int(win_match.group(2)) / 100
                left_avg_score = int(avg_score_match.group(1)) if avg_score_match else 150
                right_avg_score = int(avg_score_match.group(2)) if avg_score_match else 150
                
                # Only use if at least 2 matches played
                if left_matches >= 2:
                    print(f"[STATS] Extracted season stats for {left_team}: {left_matches} matches, {left_win_pct*100:.0f}% win rate")
                    self._inject_season_stats(left_team, left_matches, left_win_pct, left_avg_score)
                
                if right_matches >= 2:
                    print(f"[STATS] Extracted season stats for {right_team}: {right_matches} matches, {right_win_pct*100:.0f}% win rate")
                    self._inject_season_stats(right_team, right_matches, right_win_pct, right_avg_score)
                    
        except Exception as e:
            logger.warning(f"Could not extract team comparison: {e}")
    
    def _inject_season_stats(self, team_abbrev: str, matches: int, win_rate: float, avg_score: float):
        """Inject extracted season stats into the feature store's SEASON_OVERRIDES.
        
        Note: bat_first_wr and bowl_first_wr are TEAM-specific situation rates, NOT venue rates.
        We scale the team's historical situation rates by their current season win rate.
        This preserves team-specific batting/bowling first preferences.
        """
        try:
            from bbl_pipeline.features.store import InMemoryFeatureStore
            
            # Resolve full team name from abbreviation
            full_name = team_abbrev
            feature_store = getattr(self.predictor, 'feature_store', None) if hasattr(self, 'predictor') else None
            if feature_store and hasattr(feature_store, '_resolve_team_abbrev'):
                full_name = feature_store._resolve_team_abbrev(team_abbrev)
            elif team_abbrev.upper() in InMemoryFeatureStore.TEAM_ABBREVIATIONS_IPL:
                full_name = InMemoryFeatureStore.TEAM_ABBREVIATIONS_IPL[team_abbrev.upper()]
            elif team_abbrev.upper() in InMemoryFeatureStore.TEAM_ABBREVIATIONS_PSL:
                full_name = InMemoryFeatureStore.TEAM_ABBREVIATIONS_PSL[team_abbrev.upper()]
            elif team_abbrev.upper() in InMemoryFeatureStore.TEAM_ABBREVIATIONS:
                full_name = InMemoryFeatureStore.TEAM_ABBREVIATIONS[team_abbrev.upper()]
            
            # Always use team's historical situation rates scaled by current season win rate
            # This is different from venue bat_first_wr which is the same for all teams!
            bat_first_wr = None
            bowl_first_wr = None
            
            # Get feature store from predictor
            if feature_store and hasattr(feature_store, '_team_stats'):
                # Ensure feature store is loaded
                if not feature_store._loaded:
                    feature_store.load()
                # Get historical team stats for situation rates
                hist_team_stats = feature_store._team_stats.get(full_name)
                if hist_team_stats:
                    hist_wr = hist_team_stats.get('win_rate', 0.5)
                    hist_bat = hist_team_stats.get('bat_first_wr', hist_wr)
                    hist_bowl = hist_team_stats.get('bowl_first_wr', hist_wr)
                    
                    # Scale historical situation rates to current season win rate
                    # This preserves team's relative strength batting vs bowling first
                    # BUT CAP the ratio to prevent extreme values (max 1.15 = 15% boost)
                    if hist_wr > 0:
                        bat_first_ratio = min(1.15, max(0.85, hist_bat / hist_wr))  # Cap ratio to +/- 15%
                        bowl_first_ratio = min(1.15, max(0.85, hist_bowl / hist_wr))  # Cap ratio to +/- 15%
                        bat_first_wr = min(0.85, max(0.15, win_rate * bat_first_ratio))  # Also cap absolute value
                        bowl_first_wr = min(0.85, max(0.15, win_rate * bowl_first_ratio))
                        logger.info(f"Scaled team situation rates for '{full_name}': bat_first={bat_first_wr:.0%}, bowl_first={bowl_first_wr:.0%} (from historical ratios, capped)")
            
            # Final fallback to team's overall win rate
            if bat_first_wr is None:
                bat_first_wr = win_rate
            if bowl_first_wr is None:
                bowl_first_wr = win_rate
            
            # Update the class-level SEASON_OVERRIDES dictionary
            InMemoryFeatureStore.SEASON_OVERRIDES[full_name] = {
                'win_rate': win_rate,
                'matches': matches,
                'avg_score': avg_score,
                'bat_first_wr': bat_first_wr,
                'bowl_first_wr': bowl_first_wr,
            }
            logger.info(f"Injected season stats for '{full_name}': {matches} matches, {win_rate*100:.0f}% WR, bat_first={bat_first_wr:.0%}, bowl_first={bowl_first_wr:.0%}")
            
        except Exception as e:
            logger.warning(f"Could not inject season stats: {e}")
    
    async def _extract_venue_stats(self, page_text: str):
        """
        Extract venue stats from CREX info page.
        
        Example text pattern (multi-line, numbers may be adjacent to labels):
        Venue Stats
        31
        Matches
        Win Bat first
        55%
        Win Bowl first
        45%
        Avg 1st Inns163
        Avg 2st Inns147
        """
        try:
            import re
            from bbl_pipeline.features.store import InMemoryFeatureStore
            
            # More flexible patterns for multi-line format
            # Pattern 1: "Venue Stats\n31\nMatches" or "Venue Stats 31 Matches"
            venue_matches_pattern = r'Venue\s*Stats\s*(\d+)\s*Matches'
            
            # Pattern 2: "Win Bat first\n55%" or "Win Bat first 55%"
            bat_first_pattern = r'Win\s*Bat\s*first\s*[\n\r\s]*(\d+)\s*%'
            bowl_first_pattern = r'Win\s*Bowl\s*first\s*[\n\r\s]*(\d+)\s*%'
            
            # Pattern for avg innings scores: "Avg 1st Inns163" or "Avg 1st Inns 163"
            avg_1st_inns_pattern = r'Avg\s*1st\s*Inns\s*[\n\r\s]*(\d+)'
            avg_2nd_inns_pattern = r'Avg\s*2(?:st|nd)\s*Inns\s*[\n\r\s]*(\d+)'
            
            venue_matches = re.search(venue_matches_pattern, page_text, re.IGNORECASE)
            bat_first_match = re.search(bat_first_pattern, page_text, re.IGNORECASE)
            bowl_first_match = re.search(bowl_first_pattern, page_text, re.IGNORECASE)
            avg_1st_match = re.search(avg_1st_inns_pattern, page_text, re.IGNORECASE)
            avg_2nd_match = re.search(avg_2nd_inns_pattern, page_text, re.IGNORECASE)

            # CREX renders these values as separate labelled DOM elements;
            # inner_text can place the label and number apart or reverse the
            # visual order. Read the labels from the page markup as the
            # authoritative mapping, with text parsing as the fallback.
            try:
                page_markup = await self.page.content()
                dom_avg_1st = re.search(
                    r'class="venue-avg-text"[^>]*>\s*Avg\s*1st\s*Inns.*?'
                    r'class="venue-avg-val"[^>]*>\s*(\d+)',
                    page_markup, re.IGNORECASE | re.DOTALL
                )
                dom_avg_2nd = re.search(
                    r'class="venue-avg-wrap[^>]*venue-avg-sec-inn[^>]*".*?'
                    r'Avg\s*2(?:st|nd)\s*Inns.*?'
                    r'class="venue-avg-val"[^>]*>\s*(\d+)',
                    page_markup, re.IGNORECASE | re.DOTALL
                )
                if dom_avg_1st:
                    avg_1st_match = dom_avg_1st
                if dom_avg_2nd:
                    avg_2nd_match = dom_avg_2nd
            except Exception as e:
                logger.debug("Could not read labelled CREX venue elements", error=str(e))
            
            if bat_first_match and bowl_first_match:
                bat_first_wr = int(bat_first_match.group(1)) / 100
                bowl_first_wr = int(bowl_first_match.group(1)) / 100
                num_matches = int(venue_matches.group(1)) if venue_matches else 0
                avg_1st_inns = int(avg_1st_match.group(1)) if avg_1st_match else 160
                avg_2nd_inns = int(avg_2nd_match.group(1)) if avg_2nd_match else 150
                
                # Store venue situation stats
                InMemoryFeatureStore.VENUE_SITUATION_STATS = {
                    'bat_first_wr': bat_first_wr,
                    'bowl_first_wr': bowl_first_wr,
                    'matches': num_matches,
                    'avg_1st_inns': avg_1st_inns,
                    'avg_2nd_inns': avg_2nd_inns,
                }
                print(f"[VENUE] Extracted venue stats: {num_matches} matches, bat first WR {bat_first_wr*100:.0f}%, bowl first WR {bowl_first_wr*100:.0f}%")
                print(f"   Avg 1st innings: {avg_1st_inns}, Avg 2nd innings: {avg_2nd_inns}")
                logger.info(f"Injected venue situation stats: bat_first={bat_first_wr:.0%}, bowl_first={bowl_first_wr:.0%}, avg_1st={avg_1st_inns}, avg_2nd={avg_2nd_inns}")
                
        except Exception as e:
            logger.warning(f"Could not extract venue stats: {e}")

    async def _extract_on_venue_avg(self, team1: str, team2: str):
        """
        Read the optional 'On Venue' team context for diagnostics only.

        The team-specific on-venue average is not the venue first-innings
        average and must not replace the official CREX Venue Stats value used
        by inference.  The latter is extracted by _extract_venue_stats().
        """
        try:
            import re
            from bbl_pipeline.features.store import InMemoryFeatureStore

            # Try clicking the "On Venue" tab. Playwright text selectors:
            # 'text=On Venue' matches any element containing this exact text.
            clicked = False
            for selector in ['text="On Venue"', 'text=On Venue', ':text("On Venue")']:
                try:
                    await self.page.click(selector, timeout=3000)
                    clicked = True
                    break
                except Exception:
                    pass

            if not clicked:
                logger.info("[ON-VENUE] Could not find/click 'On Venue' tab — skipping on-venue avg extraction")
                return

            await asyncio.sleep(1)
            on_venue_text = await self.page.inner_text("body")

            # Extract team headers to identify left/right columns
            team_headers_pattern = r'([A-Z0-9\-]+)\s+vs\s+all\s+teams\s+([A-Z0-9\-]+)\s+vs\s+all\s+teams'
            hdr = re.search(team_headers_pattern, on_venue_text, re.IGNORECASE)
            if not hdr:
                logger.info("[ON-VENUE] Could not parse team headers after tab click")
                return

            left_abbrev = hdr.group(1)
            right_abbrev = hdr.group(2)

            # How many matches each team has played at this venue
            matches_pattern = r'(\d+)\s*Matches\s*Played\s*(\d+)'
            avg_pattern     = r'(\d+)\s*Avg\s*Score\s*(\d+)'

            matches_m = re.search(matches_pattern, on_venue_text, re.IGNORECASE)
            avg_m     = re.search(avg_pattern,     on_venue_text, re.IGNORECASE)

            if not avg_m:
                logger.info("[ON-VENUE] No 'Avg Score' found in On Venue tab")
                return

            left_matches  = int(matches_m.group(1)) if matches_m else 0
            right_matches = int(matches_m.group(2)) if matches_m else 0
            left_avg      = int(avg_m.group(1))
            right_avg     = int(avg_m.group(2))

            print(f"[ON-VENUE] {left_abbrev}: {left_avg} avg ({left_matches} venue matches), "
                  f"{right_abbrev}: {right_avg} avg ({right_matches} venue matches)")

            print(f"[ON-VENUE] Diagnostic only: {left_abbrev} {left_avg}, {right_abbrev} {right_avg}; "
                  "keeping official Venue Stats average for inference")
            logger.info("On-venue team averages are diagnostic only; official CREX venue average remains authoritative")

        except Exception as e:
            logger.warning(f"Could not extract on-venue avg: {e}")

    async def _fetch_match_info_page(self):
        """Fetch additional match info from the info page (toss, venue, etc)."""
        try:
            info_url = self._get_info_url()
            print(f"[FETCH] Fetching match info from: {info_url}")
            
            # Navigate to info page briefly
            await self.page.goto(info_url, timeout=30000)
            await asyncio.sleep(2)
            
            # Extract toss info - look for "opt to Bat" or "opt to Bowl"
            page_text = await self.page.inner_text("body")
            
            # Parse toss decision - match team abbreviations like PRS-W, SYS-W
            import re
            toss_match = re.search(r'([A-Z0-9\-]+)\s+opt\s+to\s+(Bat|Bowl)', page_text, re.IGNORECASE)
            if toss_match:
                self.match_state.toss_winner = toss_match.group(1)
                self.match_state.toss_decision = toss_match.group(2).lower()
                print(f"[TOSS] Toss: {self.match_state.toss_winner} won, elected to {self.match_state.toss_decision}")
            
            # Extract venue - look for known cricket venue patterns
            # Be specific to avoid capturing random text
            if self.venue_override:
                self.match_state.venue = self.venue_override
                print(f"[VENUE] Venue (Override): {self.match_state.venue}")
            else:
                # First, try to extract venue from the weather section (appears at top of info page)
                # Pattern: "International Sports Stadium, Coffs Harbour weather International Sports Stadium"
                # or "Adelaide Oval weather Adelaide Oval 25°C"
                weather_venue_match = re.search(r'([\w\s]+(?:Stadium|Oval|Ground|Arena|Park))(?:,\s*[\w\s]+)?\s+weather\s+\1', page_text, re.IGNORECASE)
                if weather_venue_match:
                    venue = weather_venue_match.group(1).strip()
                    venue = ' '.join(venue.split())
                    if len(venue) > 5 and len(venue) < 60:
                        self.match_state.venue = venue
                        logger.info(f"Extracted venue from weather section: '{venue}'")
                        print(f"[VENUE] Venue: {self.match_state.venue}")
                
                # If weather pattern didn't work, try specific venue patterns
                if not self.match_state.venue:
                    venue_patterns = [
                        r'Venue\s*[:\-]?\s*([\w\s]+(?:Stadium|Oval|Ground|Arena|Park))',  # "Venue: North Sydney Oval"
                        # BBL regional/special venues (prioritize specific names)
                        r'(International Sports Stadium[\w\s,]*)',  # Coffs Harbour
                        r'(C\.?ex Coffs International Stadium)',  # Alternative name
                        r'(Lavington Sports Ground)',  # Albury
                        r'(Traeger Park[\w\s,]*)',  # Alice Springs
                        # SA20 venues
                        r'(Kingsmead[\w\s,]*)',  # Durban
                        r'(Newlands[\w\s,]*)',   # Cape Town
                        r'(Boland Park[\w\s,]*)', # Paarl
                        r"(St George's Park[\w\s,]*)",  # Gqeberha
                        r'(SuperSport Park[\w\s,]*)',  # Centurion
                        r'(Wanderers[\w\s,]*)',  # Johannesburg
                        r'(Durban[\w\s]+Stadium)',
                        r'(Hollywoodbets[\w\s]+)',
                        # New Zealand venues (Super Smash)
                        r'(Basin Reserve[\w\s,]*)',
                        r'(Eden Park[\w\s,]*)',
                        r'(Hagley Oval[\w\s,]*)',
                        r'(Seddon Park[\w\s,]*)',
                        r'(Bay Oval[\w\s,]*)',
                        r'(McLean Park[\w\s,]*)',
                        r'(University of Otago Oval[\w\s,]*)',  # Dunedin - exact name
                        r'(University Oval[\w\s,]*)',  # Generic fallback
                        r'(Saxton Oval[\w\s,]*)',
                        r'(Pukekura Park[\w\s,]*)',
                        r'(Molyneux Park[\w\s,]*)',
                        r'(John Davies Oval[\w\s,]*)',
                        r'(Fitzherbert Park[\w\s,]*)',
                        r'(Cobham Oval[\w\s,]*)',
                        # Australian venues
                        r'(Simonds Stadium)',  # Specific pattern for Simonds Stadium
                        r'(Kardinia Park)',
                        r'(GMHBA Stadium)',
                        r'(North Sydney Oval)',
                        r'(Sydney Showground Stadium)',
                        r'(Adelaide Oval)',
                        r'(The Gabba|Brisbane Cricket Ground)',
                        r'(MCG|Melbourne Cricket Ground)',
                        r'(SCG|Sydney Cricket Ground)',
                        r'(WACA|Perth Stadium|Optus Stadium)',
                        r'(Bellerive Oval|Blundstone Arena)',
                        r'(Manuka Oval)',
                        r'(Junction Oval)',
                        # IPL venues (India)
                        r'(Eden Gardens[\w\s,]*)',
                        r'(Wankhede Stadium[\w\s,]*)',
                        r'(M\.?\s*A\.?\s*Chidambaram Stadium[\w\s,]*)',
                        r'(Chepauk[\w\s,]*)',
                        r'(Chinnaswamy Stadium[\w\s,]*)',
                        r'(M\.?\s*Chinnaswamy Stadium[\w\s,]*)',
                        r'(Arun Jaitley Stadium[\w\s,]*)',
                        r'(Feroz Shah Kotla[\w\s,]*)',
                        r'(Rajiv Gandhi International[\w\s,]*)',
                        r'(Uppal[\w\s,]*)',
                        r'(Sawai Mansingh Stadium[\w\s,]*)',
                        r'(Narendra Modi Stadium[\w\s,]*)',
                        r'(Motera[\w\s,]*)',
                        r'(Punjab Cricket Association[\w\s,]*)',
                        r'(IS Bindra Stadium[\w\s,]*)',
                        r'(Maharashtra Cricket Association Stadium[\w\s,]*)',
                        r'(Ekana Cricket Stadium[\w\s,]*)',
                        r'(BRSABV Ekana[\w\s,]*)',
                        r'(Bharat Ratna[\w\s,]*)',
                        r'(Himachal Pradesh Cricket Association[\w\s,]*)',
                        r'(HPCA Stadium[\w\s,]*)',
                        # UAE venues
                        r'(Dubai International Cricket Stadium)',
                        r'(Zayed Cricket Stadium[\w\s,]*)',
                        r'(Sharjah Cricket Stadium)',
                        # PSL venues
                        r'(Rawalpindi Cricket Stadium[\w\s,]*)',
                        r'(Gaddafi Stadium[\w\s,]*)',
                        r'(National Stadium[\w\s,]*)',
                        r'(Multan Cricket Stadium[\w\s,]*)',
                        # Generic patterns (last)
                        r'([\w\s]+Cricket Ground)',
                        r'([\w\s]+Cricket Stadium)',
                    ]
                    for pattern in venue_patterns:
                        venue_match = re.search(pattern, page_text, re.IGNORECASE)
                        if venue_match:
                            venue = venue_match.group(1).strip()
                            # Clean up venue - remove any newlines or extra whitespace
                            venue = ' '.join(venue.split())
                            venue = self._clean_venue_text(venue)
                            # Remove time prefixes like "45 PM" or date info
                            venue = re.sub(r'^\d+\s*(?:AM|PM)\s+', '', venue, flags=re.IGNORECASE)
                            # Remove common trailing words that get captured
                            venue = re.sub(r'\s+(Team Form|Match Info|Live|Scorecard|Commentary).*$', '', venue, flags=re.IGNORECASE)
                            # Clean trailing commas or spaces
                            venue = venue.rstrip(', ')
                            if len(venue) > 5 and len(venue) < 60:  # Reasonable venue name length
                                self.match_state.venue = venue
                                logger.info(f"Extracted venue from page: '{venue}'")
                                print(f"[VENUE] Venue: {self.match_state.venue}")
                                break

            # Venue Stats are independent of team-code resolution. Extract
            # them before the team-comparison branch so an unfamiliar code
            # (for example UGN) cannot force the inference baseline to 160.
            await self._extract_venue_stats(page_text)
            
            # Extract teams from URL first. CREX info text can include match-preview
            # article snippets directly after "CSK vs MI", which are not team names.
            teams = self._extract_teams_from_url() or self._extract_vs_teams(page_text)
            if teams:
                team1, team2 = teams
                # Store as team1 and team2 initially - batting will be set from title later
                self._team1 = team1
                self._team2 = team2
                print(f"[TEAMS] Teams: {team1} vs {team2}")
                
                # Extract team comparison stats (season form) and inject into feature store
                # This will use venue stats for situation rates if available
                await self._extract_team_comparison(page_text, team1, team2)
                
                # Click "On Venue" tab and extract both teams' on-venue avg scores.
                # Average of the two teams' venue avg = realistic match-day scoring estimate.
                await self._extract_on_venue_avg(team1, team2)
            
            # Navigate back to live page
            await self.page.goto(self.match_url, timeout=30000)
            await asyncio.sleep(3)
            
        except Exception as e:
            print(f"[WARN] Could not fetch info page: {e}")
            # Still try to go to live page
            try:
                await self.page.goto(self.match_url, timeout=30000)
                await asyncio.sleep(3)
            except:
                pass
    
    async def start(self):
        """Start the browser and navigate to match."""
        print(f"[START] Starting Crex Live Predictor")
        print(f"   Match URL: {self.match_url}")
        
        self._playwright = await async_playwright().start()

        self.browser = await self._playwright.chromium.launch(headless=self.headless)
        context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080},
        )
        
        self.page = await context.new_page()
        
        # Setup network interception for API data
        self.api_data = {}
        self.page.on("response", self._handle_response)
        
        # First fetch info page for toss, venue, etc.
        print(f"[WEB] Opening info page first...")
        await self._fetch_match_info_page()
        
        # Wait for page title to include score (retry up to 10 times)
        for _ in range(10):
            title = await self.page.title()
            if re.match(r'^(\w+)\s+(\d+)[-/](\d+)\s+\(', title):
                break
            await asyncio.sleep(1)
        
        print(f"[OK] Page loaded: {title}")
        
        # Extract localStorage for team/player code resolution
        try:
            self.local_storage = await self.page.evaluate(
                "() => Object.fromEntries(Object.entries(localStorage).map(([k, v]) => [k, v]))"
            )
            team_entries = sum(1 for k in self.local_storage if k.startswith('t_'))
            print(f"[STORE] Loaded localStorage: {len(self.local_storage)} entries ({team_entries} teams)")
        except Exception as e:
            print(f"[WARN] Could not extract localStorage: {e}")
            self.local_storage = {}
        
        # Extract initial match info from live page
        await self._extract_match_info()
        
        return True
    
    async def _handle_response(self, response):
        """Handle network responses to capture API data."""
        try:
            if "sV3" in response.url:
                data = await response.json()
                self.api_data = data
                self._process_api_data(data)
        except Exception:
            pass

    @staticmethod
    def _extract_crex_api_key(match_url: str) -> str:
        """Extract the provider match key used by CREX's sV3 endpoint."""
        value = (match_url or "").strip()
        query_match = re.search(r"(?:[?&])key=([A-Za-z0-9]+)", value, re.IGNORECASE)
        if query_match:
            return query_match.group(1)

        slug_match = re.search(
            r"match-updates-([A-Za-z0-9]+)(?:/[^/?#]*)?/?(?:[?#].*)?$",
            value,
            re.IGNORECASE,
        )
        return slug_match.group(1) if slug_match else ""

    async def _poll_crex_market_odds(self) -> None:
        """Read current market odds directly from CREX's public sV3 API.

        CREX may render the odds without exposing the XHR through the page
        response listener. The direct request keeps market evidence complete
        while retaining the page listener as a fallback. This is intentionally
        throttled because the main predictor loop runs more frequently.
        """
        if not self.page:
            return

        now = asyncio.get_running_loop().time()
        last_fetch = getattr(self, "_last_market_api_fetch_at", None)
        if last_fetch is not None and now - last_fetch < 5.0:
            return
        self._last_market_api_fetch_at = now

        api_key = self._extract_crex_api_key(self.match_url or self.original_match_url)
        if not api_key:
            return

        try:
            response = await self.page.request.get(
                f"https://api-v1.com/v10/sV3.php?key={api_key}",
                headers={
                    "Origin": "https://crex.com",
                    "Referer": "https://crex.com/",
                },
                timeout=10_000,
            )
            if not response.ok:
                logger.debug("market_odds_api_poll_non_2xx", status=response.status, key=api_key)
                return

            data = await response.json()
            if isinstance(data, dict):
                self.api_data = data
                self._process_api_data(data)
        except Exception as exc:
            # Market data is optional. A transient provider/API failure must
            # leave the row explicitly unavailable rather than stop inference.
            logger.debug("market_odds_api_poll_failed", key=api_key, error=str(exc))

    @staticmethod
    def _extract_authoritative_bowler(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract the current bowler from CrickZen's shared live snapshot.

        The live hero and predictor dashboard consume the shared
        ``last-updated-data`` contract. CREX-backed payloads have appeared with
        ``bowler_data`` as either a one-item list or a single object, while
        commentary consistently carries ``bowlerName`` and text such as
        ``Name to Batter``. Keep this parser version-tolerant and conservative:
        an empty/placeholder name is never promoted into MatchState.
        """
        if not isinstance(payload, dict):
            return None

        def clean_name(value: Any) -> str:
            name = re.sub(r"\s+", " ", str(value or "")).strip()
            if not name or name.lower() in {"unknown", "-", "n/a", "na", "bowler"}:
                return ""
            if re.search(r"\b(?:innings?|over|score|target|need|rate)\b", name, re.IGNORECASE):
                return ""
            return name

        def numeric(entry: Dict[str, Any], *keys: str) -> Optional[float]:
            for key in keys:
                value = entry.get(key)
                if value is None or isinstance(value, bool):
                    continue
                match = re.search(r"-?\d+(?:\.\d+)?", str(value))
                if match:
                    try:
                        return float(match.group(0))
                    except ValueError:
                        continue
            return None

        raw_bowler_data = payload.get("bowler_data")
        if raw_bowler_data is None:
            raw_bowler_data = payload.get("bowlerData")
        if isinstance(raw_bowler_data, dict) and isinstance(raw_bowler_data.get("data"), (dict, list)):
            raw_bowler_data = raw_bowler_data["data"]
        if isinstance(raw_bowler_data, dict):
            bowler_entries = [raw_bowler_data]
        elif isinstance(raw_bowler_data, list):
            bowler_entries = [entry for entry in raw_bowler_data if isinstance(entry, dict)]
        else:
            bowler_entries = []

        for entry in bowler_entries:
            name = clean_name(
                entry.get("name")
                or entry.get("bowlerName")
                or entry.get("bowler_name")
                or entry.get("playerName")
                or entry.get("player_name")
            )
            if not name:
                continue
            overs = numeric(entry, "overs", "oversBowled", "bowlerOvers")
            balls_bowled = numeric(entry, "ballsBowled", "balls_bowled")
            if overs is None and balls_bowled is not None:
                overs = balls_bowled / 6.0
            runs = numeric(entry, "runs", "runsConceded", "bowlerRuns", "score")
            wickets = numeric(entry, "wickets", "wicketsTaken", "bowlerWickets")
            return {
                "name": name,
                "overs": overs if overs is not None else 0.0,
                "runs": int(runs) if runs is not None else 0,
                "wickets": int(wickets) if wickets is not None else 0,
            }

        raw_commentary = payload.get("commentary") or payload.get("latest_commentary")
        if isinstance(raw_commentary, dict):
            commentary_entries = [raw_commentary]
        elif isinstance(raw_commentary, list):
            commentary_entries = [entry for entry in raw_commentary if isinstance(entry, dict)]
        else:
            commentary_entries = []

        for entry in commentary_entries:
            name = clean_name(entry.get("bowlerName") or entry.get("bowler_name"))
            if not name:
                text = str(entry.get("text") or entry.get("commentary") or "")
                match = re.match(r"\s*(.+?)\s+to\s+", text, re.IGNORECASE)
                name = clean_name(match.group(1) if match else "")
            if name:
                return {"name": name, "overs": 0.0, "runs": 0, "wickets": 0}

        return None

    async def _hydrate_current_bowler_from_shared_snapshot(self) -> None:
        """Bridge the shared live bowler payload into the predictor state.

        Direct CREX DOM extraction remains the first path. This bounded
        fallback uses the same backend snapshot already consumed by the live
        hero, so evidence and public display can no longer disagree merely
        because the predictor's page selectors missed the current row.
        """
        if not self.page:
            return

        now = asyncio.get_running_loop().time()
        last_fetch = getattr(self, "_last_bowler_api_fetch_at", None)
        if last_fetch is not None and now - last_fetch < 5.0:
            return
        self._last_bowler_api_fetch_at = now

        endpoint = os.getenv(
            "CRICKZEN_BOWLER_DATA_ENDPOINT",
            "https://www.crickzen.com/api/cricket-data/last-updated-data",
        ).strip()
        if not endpoint:
            return
        source_url = self.match_url or self.original_match_url
        if not source_url:
            return
        separator = "&" if "?" in endpoint else "?"
        request_url = f"{endpoint}{separator}url={quote(source_url, safe='')}"

        try:
            response = await self.page.request.get(request_url, timeout=5_000)
            if not response.ok:
                logger.debug("shared_bowler_snapshot_non_2xx", status=response.status)
                return
            payload = await response.json()
            bowler = self._extract_authoritative_bowler(payload)
            if not bowler:
                return
            self.match_state.bowler1_name = bowler["name"]
            self.match_state.bowler1_overs = bowler["overs"]
            self.match_state.bowler1_runs = bowler["runs"]
            self.match_state.bowler1_wickets = bowler["wickets"]
            self.match_state.bowler_data_source = "crickzen_shared_live_snapshot"
        except Exception as exc:
            # Bowler enrichment is optional. A transient backend failure must
            # not stop inference or erase a direct CREX value.
            logger.debug("shared_bowler_snapshot_failed", error=str(exc))

    def _process_api_data(self, data: Dict[str, Any]):
        """Process sV3 API data into match state."""
        try:
            # Current ball info (field B)
            if "B" in data:
                raw_b = str(data["B"])
                self.match_state.current_ball = raw_b
            
            # Extract overs data from rb field
            rb_field = data.get("rb") or data.get("rbl")
            if rb_field and isinstance(rb_field, list):
                for over_obj in rb_field:
                    if not isinstance(over_obj, dict):
                        continue
                    
                    o_num = over_obj.get("o", 0)
                    balls_data = over_obj.get("b", [])
                    
                    for i, b_obj in enumerate(balls_data):
                        ball_num = f"{o_num}.{i+1}"
                        
                        if isinstance(b_obj, dict):
                            u_val = str(b_obj.get("u", "0"))
                            # Also check for explicit wicket field
                            has_wicket_field = b_obj.get("w") == 1 or b_obj.get("wicket") == 1
                        else:
                            u_val = str(b_obj)
                            has_wicket_field = False
                        
                        # Parse runs
                        runs = 0
                        # Detect wicket from multiple formats: W, w, OUT, or explicit wicket field
                        # Be careful NOT to match "WD" (wide) or "1W" (runs + wide) as wickets
                        u_upper = u_val.upper()
                        is_wide = "WD" in u_upper or u_upper.endswith("W") and u_upper != "W"  # e.g. "1W" = 1 wide
                        is_wicket = (u_upper in ("W", "OUT") or has_wicket_field) and not is_wide
                        is_dot = u_val == "0"
                        is_boundary = u_val == "4"
                        is_six = u_val == "6"
                        
                        if u_val.isdigit():
                            runs = int(u_val)
                        
                        ball = BallData(
                            ball_number=ball_num,
                            over_number=o_num,
                            ball_in_over=i+1,
                            runs=runs,
                            is_wicket=is_wicket,
                            is_dot=is_dot,
                            is_boundary=is_boundary,
                            is_six=is_six,
                            extras=0,
                            extras_type=None,
                            commentary="",
                            batsman_name="",
                            bowler_name=""
                        )
                        
                        # Add to balls data if new
                        if not any(b.ball_number == ball_num for b in self.match_state.balls_data):
                            self.match_state.balls_data.append(ball)
                            
            # Extract market odds from API (fields F and R)
            # F = Favorite team code, R = Odds in format "back+diff"
            # CREX uses t_H_name / t_M_name in localStorage where H=first-team and M=second-team.
            fav_team_code = str(data.get("F") or "").replace("^", "").strip()
            r_raw = data.get("R", "")
            if fav_team_code or r_raw:
                logger.debug(
                    "market_odds_received",
                    F=data.get("F"), fav_code=fav_team_code, R=r_raw,
                    ls_lookup=self.local_storage.get(f"t_{fav_team_code}_name"),
                    team2=getattr(self, "_team2", None),
                )
            if fav_team_code:
                # Resolve team code to name using localStorage.
                # Some payloads briefly carry non-team values (e.g. "1I").
                # Do not overwrite with unresolved code strings.
                fav_team_name = self.local_storage.get(f"t_{fav_team_code}_name")
                if not fav_team_name:
                    # Fallback: CREX uses H=home (first in URL) and M=match/away (second in URL).
                    code_upper = fav_team_code.upper()
                    if code_upper == "H":
                        fav_team_name = getattr(self, "_team1", None)
                    elif code_upper == "M":
                        fav_team_name = getattr(self, "_team2", None)
                if not fav_team_name:
                    resolved_fav_team = self._resolve_team_name(fav_team_code)
                    if self._looks_like_valid_team_name(resolved_fav_team):
                        fav_team_name = resolved_fav_team
                if fav_team_name:
                    self.match_state.market_fav_team = fav_team_name
            
            r_val = data.get("R", "")
            if r_val:
                r_str = str(r_val)
                if "+" in r_str:
                    parts = r_str.split("+")
                    back = parts[0]
                    diff = parts[1] if len(parts) > 1 else "0"
                    try:
                        lay = str(int(back) + int(diff))
                        self.match_state.market_back_odds = back
                        self.match_state.market_lay_odds = lay
                        # Calculate implied probability: 100 / (100 + odds)
                        # E.g., odds of 90 means favorite has ~52.6% implied prob
                        back_int = int(back)
                        if back_int > 0:
                            self.match_state.market_fav_prob = 100.0 / (100.0 + back_int)
                            self._last_market_update_at = datetime.now()
                            self._last_market_age_seconds = 0.0
                    except ValueError:
                        pass
                else:
                    self.match_state.market_back_odds = r_str
                    self.match_state.market_lay_odds = r_str
                    try:
                        back_int = int(r_str)
                        if back_int > 0:
                            self.match_state.market_fav_prob = 100.0 / (100.0 + back_int)
                            self._last_market_update_at = datetime.now()
                            self._last_market_age_seconds = 0.0
                    except ValueError:
                        pass
                        
        except Exception as e:
            print(f"[WARN] Error processing API data: {e}")
    
    @staticmethod
    def _extract_score_snapshot(
        text: str,
        preferred_team: str | None = None,
    ) -> tuple[str, int, int, float] | None:
        """Extract the current CREX score from title or visible score rows.

        CREX normally publishes the score in ``document.title``. During a
        client-side refresh, however, the title can briefly lag while the
        visible score card already contains rows such as ``PD``, ``71-2``,
        ``5.3``. Keep this parser independent of Playwright so both shapes are
        covered by unit tests and so a transient title mismatch cannot publish
        a default ``0/0`` state.
        """
        if not text:
            return None

        cleaned = str(text).replace("\u00a0", " ")
        title_match = re.search(
            r"(?m)^\s*(?P<team>[A-Za-z0-9][A-Za-z0-9&.'\- ]*?)\s+"
            r"(?P<runs>\d{1,4})\s*[-/]\s*(?P<wickets>\d{1,2})\s*"
            r"\(\s*(?P<overs>\d{1,3}(?:\.\d+)?)\s*\)",
            cleaned,
        )
        candidates: list[tuple[str, int, int, float]] = []
        if title_match:
            candidates.append(
                (
                    title_match.group("team").strip(),
                    int(title_match.group("runs")),
                    int(title_match.group("wickets")),
                    float(title_match.group("overs")),
                )
            )

        # The hydrated score card is rendered as three adjacent text rows.
        # Parse by line instead of flattening the whole page, which avoids
        # mistaking commentary/history score lines for the current score.
        lines = [re.sub(r"\s+", " ", line).strip() for line in cleaned.splitlines()]
        for index in range(len(lines) - 2):
            score_match = re.fullmatch(
                r"(?P<runs>\d{1,4})\s*[-/]\s*(?P<wickets>\d{1,2})",
                lines[index + 1],
            )
            overs_match = re.fullmatch(r"(?P<overs>\d{1,3}(?:\.\d+)?)", lines[index + 2])
            team = lines[index]
            if score_match and overs_match and team and len(team) <= 60:
                candidates.append(
                    (
                        team,
                        int(score_match.group("runs")),
                        int(score_match.group("wickets")),
                        float(overs_match.group("overs")),
                    )
                )

        # Some CREX responses arrive as a compact text fragment rather than
        # line-preserving innerText. Keep a conservative inline fallback.
        compact_match = re.search(
            r"(?P<team>[A-Za-z0-9][A-Za-z0-9&.'\- ]*?)\s+"
            r"(?P<runs>\d{1,4})\s*[-/]\s*(?P<wickets>\d{1,2})\s*"
            r"\(?\s*(?P<overs>\d{1,3}\.\d+)\s*\)?",
            re.sub(r"\s+", " ", cleaned),
        )
        if compact_match:
            candidates.append(
                (
                    compact_match.group("team").strip(),
                    int(compact_match.group("runs")),
                    int(compact_match.group("wickets")),
                    float(compact_match.group("overs")),
                )
            )

        if not candidates:
            return None

        preferred_key = re.sub(r"[^A-Z0-9]", "", (preferred_team or "").upper())
        if preferred_key:
            for candidate in candidates:
                candidate_key = re.sub(r"[^A-Z0-9]", "", candidate[0].upper())
                if candidate_key == preferred_key or candidate_key.startswith(preferred_key):
                    return candidate
        return candidates[0]

    async def _extract_match_info(self):
        """Extract match information from DOM using Crex selectors."""
        try:
            # PRIMARY: Extract from page title (most reliable - Crex always updates title)
            title = await self.page.title()
            # Title format: "PRS-W 66-1 (7.2) (Sophie Devine 0(0), Beth Mooney 22(14)) vs Sydney..."
            # Extract score first
            title_score = self._extract_score_snapshot(title)
            if title_score:
                title_team, title_runs, title_wickets, title_overs = title_score
                current_batting_team = (
                    self._resolve_scorecard_team_from_provider_pair(title_team)
                    or self._resolve_team_name(title_team)
                )
                self.match_state.total_runs = title_runs
                self.match_state.wickets = title_wickets
                self.match_state.overs = title_overs
                
                # Auto-detect ODI from current overs > 20 (can't be T20 if over 20 bowled)
                current_overs = self.match_state.overs
                if current_overs > 20.0 and (self._effective_total_overs is None or self._effective_total_overs <= 20):
                    logger.info(f"Auto-detected ODI format: current overs {current_overs} > 20")
                    self._update_total_overs(50)
                
                # Auto-detect ODI from first innings overs in title: "vs Team 259-7 ((42.0))"
                first_inn_title = re.search(
                    r'vs\s+(?P<team>[A-Za-z0-9&.\'\- ]+)\s+'
                    r'(?P<runs>\d+)-\d+\s+\(\((?P<overs>[\d.]+)\)\)',
                    title,
                )
                if first_inn_title:
                    first_inn_team = (
                        self._resolve_scorecard_team_from_provider_pair(first_inn_title.group("team"))
                        or self._resolve_team_name(first_inn_title.group("team"))
                    )
                    first_inn_overs = float(first_inn_title.group("overs"))
                    first_inn_score = int(first_inn_title.group("runs"))
                    if first_inn_overs > 20.0 and (self._effective_total_overs is None or self._effective_total_overs <= 20):
                        logger.info(f"Auto-detected ODI format from title: first innings {first_inn_overs} overs (score: {first_inn_score})")
                        self._update_total_overs(50)
                    # Also set second innings info
                    if (
                        not self.match_state.is_second_innings
                        and self._second_innings_is_supported(
                            current_batting_team,
                            self.match_state.total_runs,
                            first_inn_team,
                            first_inn_score,
                        )
                    ):
                        logger.info("Innings change detected from title (first innings score found)")
                        self.match_state.is_second_innings = True
                        if self.match_state.target is None:
                            self.match_state.target = first_inn_score + 1
                            logger.info(f"Set target from title: {first_inn_score} + 1 = {self.match_state.target}")
                
                # If batting team changed, update bowling team accordingly
                if self.match_state.batting_team and self._normalize_team_key(self.match_state.batting_team) != self._normalize_team_key(current_batting_team):
                    # The current batting was the previous bowling
                    self.match_state.bowling_team = self.match_state.batting_team
                elif not self.match_state.bowling_team:
                    # First time setting teams - use info page teams if available
                    if hasattr(self, '_team1') and hasattr(self, '_team2'):
                        if self._normalize_team_key(current_batting_team) == self._normalize_team_key(self._team1):
                            self.match_state.bowling_team = self._team2
                        elif self._normalize_team_key(current_batting_team) == self._normalize_team_key(self._team2):
                            self.match_state.bowling_team = self._team1
                
                self.match_state.batting_team = current_batting_team
            else:
                # Fallback: If match hasn't started, use teams from info page
                if hasattr(self, '_team1') and hasattr(self, '_team2'):
                    self.match_state.batting_team = self._team1
                    self.match_state.bowling_team = self._team2
                else:
                    teams = self._extract_teams_from_url() or self._extract_vs_teams(title)
                    if teams:
                        self.match_state.batting_team, self.match_state.bowling_team = teams
            
            # Extract live batters from title when CREX includes "Name R(B)" pairs.
            self._apply_batter_pair(self._extract_batter_pair(title))
            
            # Get page text to detect second innings and extract data
            page_text = await self.page.inner_text("body")
            body_score = self._extract_score_snapshot(page_text)
            if body_score and (
                not title_score
                or body_score[3] > self.match_state.overs
                or body_score[1] > self.match_state.total_runs
            ):
                current_batting_team = (
                    self._resolve_scorecard_team_from_provider_pair(body_score[0])
                    or self._resolve_team_name(body_score[0])
                )
                self.match_state.total_runs = body_score[1]
                self.match_state.wickets = body_score[2]
                self.match_state.overs = body_score[3]
                title_score = body_score
                if self.match_state.batting_team and self._normalize_team_key(self.match_state.batting_team) != self._normalize_team_key(current_batting_team):
                    self.match_state.bowling_team = self.match_state.batting_team
                self.match_state.batting_team = current_batting_team
            self._capture_first_innings_summary(page_text)
            try:
                # Historical innings summaries may be present only in the SSR
                # payload, not in the hydrated visible body.
                page_html = await self.page.content()
            except Exception:
                page_html = ""
            if not self.match_state.batsman1_balls or not self.match_state.batsman2_balls:
                self._apply_batter_pair(self._extract_batter_pair(page_text))
            
            # --- DLS / Reduced-over auto-detection ---
            # Detect revised target (e.g. "Revised Target: 156 (DLS)" or "Target: 156 (D/L)")
            dls_target_match = re.search(
                r'(?:revised\s+)?target\s*[:\-]\s*(\d+)\s*\(?(?:d/?l/?s?|dls)\)?',
                page_text, re.IGNORECASE
            )
            if dls_target_match and self._cli_revised_target is None:
                detected_target = int(dls_target_match.group(1))
                if self._cli_revised_target != detected_target:
                    logger.info(f"CREX detected DLS revised target: {detected_target}")
                    self._cli_revised_target = detected_target
            
            # Detect overs format (e.g. "15 overs match", "50 overs per side")
            reduced_overs_match = re.search(
                r'(\d+)\s+ov(?:er)?s?\s+(?:match|per\s+side|a\s+side)',
                page_text, re.IGNORECASE
            )
            if reduced_overs_match:
                detected_overs = int(reduced_overs_match.group(1))
                if 1 <= detected_overs <= 50:
                    prev = self._effective_total_overs or self.format_config.total_overs
                    if detected_overs != prev:
                        logger.info(f"CREX detected overs format: {detected_overs} (was: {prev})")
                        self._update_total_overs(detected_overs)
            
            # Detect second innings by looking for "need X runs" or "RRR"
            needs_runs_match = re.search(r'need\s+(\d+)\s+runs?\s+(?:in|from)\s+(\d+)\s+balls?', page_text, re.IGNORECASE)
            rrr_match = re.search(r'RRR\s*:\s*([\d.]+)', page_text)
            
            # Also try to extract the first innings total from "vs Team XXX-Y" or "((overs))" pattern
            # Pattern: "vs Sydney Sixers 113-5 ((11.0))" -> target = 114
            first_innings_match = re.search(
                r'vs\s+(?P<team>[A-Za-z0-9&.\'\- ]+)\s+'
                r'(?P<runs>\d+)-\d+\s+\(\((?P<overs>[\d.]+)\)\)',
                page_text,
            )
            
            # Auto-detect ODI format from first innings overs (e.g. ((42.0)) means > 20 overs = ODI)
            if first_innings_match:
                first_inn_overs = float(first_innings_match.group("overs"))
                if first_inn_overs > 20 and (self._effective_total_overs is None or self._effective_total_overs <= 20):
                    detected_total = 50  # Standard ODI
                    logger.info(f"Auto-detected ODI format from first innings overs: {first_inn_overs} -> {detected_total} overs")
                    self._update_total_overs(detected_total)
            
            first_inn_team = ""
            first_inn_score = -1
            if first_innings_match:
                first_inn_team = (
                    self._resolve_scorecard_team_from_provider_pair(first_innings_match.group("team"))
                    or self._resolve_team_name(first_innings_match.group("team"))
                )
                first_inn_score = int(first_innings_match.group("runs"))
            second_innings_supported = self._second_innings_is_supported(
                current_batting_team=self.match_state.batting_team,
                current_runs=self.match_state.total_runs,
                first_innings_team=first_inn_team,
                first_innings_runs=first_inn_score,
                has_needs_runs=bool(needs_runs_match),
                has_required_run_rate=bool(rrr_match),
            )

            if second_innings_supported:
                # Note: We do NOT clear balls_data here anymore!
                # The _build_ball_history_for_mapper function handles innings filtering
                # by detecting the innings boundary (over number reset)
                if not self.match_state.is_second_innings:
                    logger.info("Innings change detected - will filter ball history in _build_ball_history_for_mapper")
                self.match_state.is_second_innings = True
                
                # Set target from "need X runs" if available
                if needs_runs_match:
                    runs_needed = int(needs_runs_match.group(1))
                    # Target = current_score + runs_needed
                    self.match_state.target = self.match_state.total_runs + runs_needed
                # Otherwise, set target from first innings score (if not already set)
                elif first_innings_match and self.match_state.target is None:
                    self.match_state.target = first_inn_score + 1  # Target = first innings + 1
                    logger.info(f"Set target from first innings score: {first_inn_score} + 1 = {self.match_state.target}")
                    
                if rrr_match:
                    self.match_state.required_run_rate = float(rrr_match.group(1))

            # Run once more after target/innings detection so a restarted
            # second-innings page can validate its first-innings summary.
            self._capture_first_innings_summary(f"{page_text}\n{page_html}")
            # This is enrichment only. Do not block the first live state on a
            # best-effort historical commentary API (the old loop could wait
            # up to 12.5 minutes before publishing the already-parsed score).
            try:
                await asyncio.wait_for(
                    self._hydrate_inn1_from_crex_over_api(),
                    timeout=5.0,
                )
            except asyncio.TimeoutError:
                logger.warning("CREX first-innings hydration timed out; continuing with live DOM state")
            except Exception as exc:
                logger.warning(f"CREX first-innings hydration skipped: {exc}")
            
            # Extract bowling team from page text if not already set
            if not self.match_state.bowling_team or self.match_state.bowling_team == self.match_state.batting_team:
                # First try using stored teams from info page
                if hasattr(self, '_team1') and hasattr(self, '_team2'):
                    if self._normalize_team_key(self.match_state.batting_team) == self._normalize_team_key(self._team1):
                        self.match_state.bowling_team = self._team2
                    elif self._normalize_team_key(self.match_state.batting_team) == self._normalize_team_key(self._team2):
                        self.match_state.bowling_team = self._team1
                
                # If still not set, look for "vs TEAM" pattern - "PRS-W vs SYS-W"
                if not self.match_state.bowling_team or self.match_state.bowling_team == self.match_state.batting_team:
                    teams = self._extract_teams_from_url() or self._extract_vs_teams(page_text) or self._extract_vs_teams(title)
                    if teams:
                        team1, team2 = teams
                        # The batting team is from title, bowling is the other
                        if self._normalize_team_key(self.match_state.batting_team) == self._normalize_team_key(team1):
                            self.match_state.bowling_team = team2
                        elif self._normalize_team_key(self.match_state.batting_team) == self._normalize_team_key(team2):
                            self.match_state.bowling_team = team1
                        else:
                            # Fuzzy match - batting team might be abbreviated differently
                            if self._normalize_team_key(team1).startswith(self._normalize_team_key(self.match_state.batting_team)[:3]):
                                self.match_state.bowling_team = team2
                            else:
                                self.match_state.bowling_team = team1

            self._repair_match_teams_from_url()
            
            # Calculate run rate
            if self.match_state.overs > 0:
                self.match_state.current_run_rate = round(
                    self.match_state.total_runs / self.match_state.overs, 2
                )
            
            # Extract batsman data from DOM (fallback if title parsing didn't work)
            if not self.match_state.batsman1_name or self.match_state.batsman1_name == "Unknown":
                batsman_rows = await self.page.query_selector_all(".batsman-row, .bat-bowl-row")
                for i, row in enumerate(batsman_rows[:2]):
                    name_el = await row.query_selector(".player-name, .name")
                    runs_el = await row.query_selector(".runs, .score")
                    balls_el = await row.query_selector(".balls, .ball")
                    
                    if name_el and runs_el:
                        name = await name_el.inner_text()
                        runs = await runs_el.inner_text()
                        balls = await balls_el.inner_text() if balls_el else "0"
                        
                        if i == 0:
                            self.match_state.batsman1_name = name.strip()
                            self.match_state.batsman1_runs = int(runs) if runs.isdigit() else 0
                            self.match_state.batsman1_balls = int(balls) if balls.isdigit() else 0
                        else:
                            self.match_state.batsman2_name = name.strip()
                            self.match_state.batsman2_runs = int(runs) if runs.isdigit() else 0
                            self.match_state.batsman2_balls = int(balls) if balls.isdigit() else 0
            
            # Extract bowler data from DOM
            # CREX current layout commonly exposes bowler as: <span class="batsmen-score bowler">D Parashar 0-1 (0.4)</span>
            bowler_text_el = await self.page.query_selector(".batsmen-score.bowler")
            if bowler_text_el:
                bowler_text = (await bowler_text_el.inner_text()).strip()
                bowler_match = re.search(r'([A-Za-z.\-]+(?:\s+[A-Za-z.\-]+)*)\s+(\d+)-(\d+)\s*\(([\d.]+)\)', bowler_text)
                if bowler_match:
                    self.match_state.bowler1_name = bowler_match.group(1).strip()
                    try:
                        self.match_state.bowler1_wickets = int(bowler_match.group(2))
                        self.match_state.bowler1_runs = int(bowler_match.group(3))
                        self.match_state.bowler1_overs = float(bowler_match.group(4))
                    except:
                        pass

            await self._hydrate_current_bowler_from_shared_snapshot()
            self._clear_invalid_current_bowler()

            # Fallback DOM selectors (legacy layouts)
            if not self.match_state.bowler1_name:
                bowler_row = await self.page.query_selector(".bowler-row, .bowl-row")
                if bowler_row:
                    name_el = await bowler_row.query_selector(".player-name, .name")
                    overs_el = await bowler_row.query_selector(".overs, .over")
                    runs_el = await bowler_row.query_selector(".runs, .score")
                    wickets_el = await bowler_row.query_selector(".wickets, .wkt")
                    
                    if name_el:
                        self.match_state.bowler1_name = (await name_el.inner_text()).strip()
                    if overs_el:
                        overs_text = await overs_el.inner_text()
                        try:
                            self.match_state.bowler1_overs = float(overs_text)
                        except:
                            pass
                    if runs_el:
                        runs_text = await runs_el.inner_text()
                        try:
                            self.match_state.bowler1_runs = int(runs_text)
                        except:
                            pass
                    if wickets_el:
                        wickets_text = await wickets_el.inner_text()
                        try:
                            self.match_state.bowler1_wickets = int(wickets_text)
                        except:
                            pass

            self._clear_invalid_current_bowler()

            # Fallback from active player card text (current CREX layout)
            if not self.match_state.bowler1_name:
                active_card = await self.page.query_selector(".player-active, .player-card, .player-profile")
                if active_card:
                    active_text = (await active_card.inner_text()).replace("\n", " ")
                    # Example: "A Markram 1 (1) + Q de Kock 0 (5) D Parashar 0-1 (0.4)"
                    card_match = re.search(r'([A-Za-z.\-]+(?:\s+[A-Za-z.\-]+)*)\s+(\d+)-(\d+)\s*\(([\d.]+)\)', active_text)
                    if card_match:
                        self.match_state.bowler1_name = card_match.group(1).strip()
                        try:
                            self.match_state.bowler1_wickets = int(card_match.group(2))
                            self.match_state.bowler1_runs = int(card_match.group(3))
                            self.match_state.bowler1_overs = float(card_match.group(4))
                        except:
                            pass

            self._clear_invalid_current_bowler()
            # Note: If DOM selectors fail, fallback regex patterns below will attempt extraction
            
            # Fallback: Try to extract bowler from page text patterns
            if not self.match_state.bowler1_name or self.match_state.bowler1_name == "Unknown":
                # Pattern 0: Current CREX figure format "Name 0-1 (0.4)"
                bowler_match = re.search(r'([A-Za-z.\-]+(?:\s+[A-Za-z.\-]+)*)\s+(\d+)-(\d+)\s*\(([\d.]+)\)', page_text)
                if bowler_match:
                    self.match_state.bowler1_name = bowler_match.group(1).strip()
                    try:
                        self.match_state.bowler1_wickets = int(bowler_match.group(2))
                        self.match_state.bowler1_runs = int(bowler_match.group(3))
                        self.match_state.bowler1_overs = float(bowler_match.group(4))
                    except:
                        pass

                # Pattern 1: Bowling figures "Player Name 1-0-8-0" or "Name 2.3-0-15-1"
                bowler_match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+([\d.]+)-\d+-\d+-\d+', page_text)
                if bowler_match and (not self.match_state.bowler1_name or self.match_state.bowler1_name == "Unknown"):
                    self.match_state.bowler1_name = bowler_match.group(1).strip()
                else:
                    # Pattern 2: "Bowler: Name" or "Bowling: Name"
                    bowler_match = re.search(r'Bowl(?:er|ing)\s*[:]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', page_text, re.IGNORECASE)
                    if bowler_match:
                        self.match_state.bowler1_name = bowler_match.group(1).strip()
                    else:
                        # Pattern 3: Extract from page title if bowler is mentioned after "vs" pattern
                        # Some CREX pages show "Team1 vs Team2 (Batsman1 X(Y), Batsman2 X(Y)) - Bowler A-B-C-D"
                        title_bowler = re.search(r'-\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+[\d.]+-\d+-\d+-\d+', title)
                        if title_bowler:
                            self.match_state.bowler1_name = title_bowler.group(1).strip()

            self._clear_invalid_current_bowler()
                        
        except Exception as e:
            print(f"[WARN] Error extracting match info: {e}")
    
    def _update_total_overs(self, new_total_overs: int) -> None:
        """Switch to a different total_overs mid-match (e.g. rain interruption).
        
        Rebuilds the format config and logs the transition.
        CLI override takes priority — this only applies to auto-detected changes.
        """
        if self._cli_total_overs is not None:
            # CLI explicitly set — don't auto-switch
            return
        
        if new_total_overs == self._effective_total_overs:
            return
        
        old = self._effective_total_overs or self.format_config.total_overs
        self._effective_total_overs = new_total_overs
        
        if new_total_overs < 20:
            self.format_config = FormatConfig.t20_reduced(new_total_overs)
            logger.info(
                f"Switching to MC-only mode: total_overs={new_total_overs} "
                f"(was {old}), par={self.format_config.par_score:.1f}"
            )
        elif new_total_overs >= 40:
            # Detect gender from league for correct par score
            odi_gender = "female" if self.league and "female" in self.league else "male"
            self.format_config = FormatConfig.odi(gender=odi_gender)
            logger.info(
                f"Switching to ODI mode ({odi_gender}): total_overs={new_total_overs} "
                f"(was {old}), par={self.format_config.par_score:.1f}"
            )
        else:
            self.format_config = FormatConfig.from_league(self.league) if self.league else FormatConfig.t20()
            logger.info(f"Reverting to standard mode: total_overs={new_total_overs} (was {old})")
    
    async def poll_and_predict(self) -> Optional[float]:
        """Poll for updates and run prediction."""
        if not self.page:
            return None
        
        try:
            self._poll_count += 1

            # CREX's live page does not consistently expose sV3 through the
            # Playwright response listener. Poll the public provider endpoint
            # directly so market evidence is available for the same state.
            await self._poll_crex_market_odds()

            # Refresh localStorage every 10 polls so team/player codes get populated
            # even if they were not ready when start() loaded the page.
            if self._poll_count % 10 == 0 or (
                not self.match_state.market_fav_team and self._poll_count <= 30
            ):
                try:
                    new_ls = await self.page.evaluate(
                        "() => Object.fromEntries(Object.entries(localStorage).map(([k, v]) => [k, v]))"
                    )
                    if new_ls:
                        self.local_storage = new_ls
                except Exception:
                    pass

            # Refresh match state from DOM
            await self._extract_match_info()
            
            # Run prediction if model is loaded or MC-only mode
            effective_overs = self._effective_total_overs or self.format_config.total_overs
            can_predict = self.model or self.mc_only or effective_overs < 20
            if can_predict:
                win_prob = self._run_prediction()
                return win_prob
            
            return None
            
        except Exception as e:
            print(f"[WARN] Error in poll_and_predict: {e}")
            return None
    
    def _is_match_complete(self) -> bool:
        """
        Check if match is completely finished.
        
        Returns True only if:
        - Innings 1 complete: all overs bowled OR all out (10 wickets)
        - Innings 2 complete: target reached OR all out OR all overs bowled
        """
        state = self.match_state
        total_overs = float(self.format_config.total_overs)
        
        if not state.is_second_innings:
            # Innings 1: complete when all overs bowled or all out
            if state.overs >= total_overs or state.wickets >= 10:
                return True
            return False
        
        # Innings 2: complete when result is determined
        if not state.target:
            # Target not yet set - still in Innings 1 or early Innings 2
            return False
        
        # Batting team won - scored enough
        if state.total_runs >= state.target:
            return True
        
        # Bowling team won - all out or all overs
        if state.wickets >= 10 or state.overs >= float(self.format_config.total_overs):
            return True
        
        return False  # Still in progress

    def _check_match_result(self) -> Optional[float]:
        """
        Check if match is definitively over and return final probability.
        Returns:
            1.0 if batting team won
            0.0 if bowling team won
            None if match still in progress
        """
        state = self.match_state
        
        # Second innings scenarios
        if state.is_second_innings and state.target:
            # Batting team won - scored enough runs
            if state.total_runs >= state.target:
                return 1.0
            
            # Bowling team won - innings complete and target not reached
            # All out (10 wickets) or all overs bowled
            if state.wickets >= 10:
                return 0.0
            if state.overs >= float(self.format_config.total_overs):
                return 0.0
            
            # Match tied - score equals target-1 at end of innings
            # (This is rare but handle it)
            
        # First innings - can't determine winner yet
        # (unless all out or 20 overs, but that just ends the innings)
        
        return None  # Match still in progress
    
    def _load_mc_calibrator(self):
        """Lazily load MC calibrator (innings×phase, innings-specific, or legacy) if available."""
        if self._mc_calibrator is not None:
            return self._mc_calibrator
        try:
            from bbl_pipeline.calibration.mc_calibrator import MCCalibrator, InningsMCCalibrators, InningsPhaseCalibrators
            import os

            # Directories to search: model_dir first, then ODI fallback
            search_dirs = [self.model_dir]
            effective_overs = self._effective_total_overs or self.format_config.total_overs
            if effective_overs >= 40:
                is_female = self.league and "female" in self.league
                # Try gender-specific fallback first
                if is_female and os.path.isdir("models/odi_female_mc_v1"):
                    search_dirs.append("models/odi_female_mc_v1")
                if os.path.isdir("models/odi_mc_v1"):
                    search_dirs.append("models/odi_mc_v1")

            for search_dir in search_dirs:
                # Prefer innings × phase calibrators (supports ODI 4-phase)
                phase_path = os.path.join(search_dir, "mc_calibrators_innings_phase.pkl")
                if os.path.exists(phase_path):
                    self._mc_calibrator = InningsPhaseCalibrators.load(phase_path)
                    logger.info(f"Loaded innings×phase MC calibrators from {search_dir}:\n{self._mc_calibrator.summary()}")
                    return self._mc_calibrator

                # Prefer innings-specific calibrators
                innings_path = os.path.join(search_dir, "mc_calibrators_innings.pkl")
                if os.path.exists(innings_path):
                    self._mc_calibrator = InningsMCCalibrators.load(innings_path)
                    logger.info(f"Loaded innings-specific MC calibrators from {search_dir}:\n{self._mc_calibrator.summary()}")
                    return self._mc_calibrator

                # Fall back to legacy single calibrator
                cal_path = os.path.join(search_dir, "mc_calibrator.pkl")
                if os.path.exists(cal_path):
                    self._mc_calibrator = MCCalibrator.load(cal_path)
                    logger.info(f"Loaded MC calibrator (legacy) from {search_dir}: {self._mc_calibrator.summary()}")
                    return self._mc_calibrator

            logger.info("No MC calibrator found — using raw MC probabilities")
            self._mc_calibrator = False  # sentinel: tried but not found
        except Exception as e:
            logger.warning(f"Failed to load MC calibrator: {e}")
            self._mc_calibrator = False
        return self._mc_calibrator
    
    def _run_reduced_over_prediction(self) -> Optional[float]:
        """MC-only prediction for reduced-over matches.
        
        Bypasses the trained model (calibrated on 20-over data) and uses
        Monte Carlo simulation directly. Platt calibration is applied
        inside the simulation engine (to the aggregated mean, not individual
        terminal states) — NOT applied again here to avoid double-calibration.
        
        Returns:
            Win probability for the batting team (0-1), or None on error.
        """
        try:
            mc_result = self._run_monte_carlo_simulation(
                model_prob=None,
                use_ml_model=self.use_ml_model,
            )
            if not mc_result or not mc_result.get("available"):
                logger.warning("MC simulation unavailable for reduced-over prediction")
                return None
            
            # Use 6-ball sim as primary (most stable for betting).
            # NOTE: mean_prob is already Platt-calibrated inside the
            # simulation engine (applied to aggregated mean probability).
            # Do NOT apply the calibrator again here — that would be
            # double-calibration.
            win_prob = mc_result["simulation_6ball"]["mean_prob"]
            raw_mean = mc_result["simulation_6ball"].get("raw_mean")
            
            mode_label = "MC-only" if self.mc_only else "Reduced-over MC"
            calibrator = self._load_mc_calibrator()
            cal_status = "engine-calibrated" if (calibrator and calibrator is not False) else "uncalibrated"
            cal_shift = f" (raw={raw_mean:.4f}, shift={win_prob - raw_mean:+.4f})" if raw_mean is not None else ""
            logger.info(
                f"{mode_label} ({cal_status}): prob={win_prob:.4f}{cal_shift} "
                f"(total_overs={self._effective_total_overs or self.format_config.total_overs})"
            )
            
            # Store MC-derived probabilities for output chain
            # raw_mean is the pre-calibration probability, win_prob is post-calibration
            self.last_raw_prob = raw_mean if raw_mean is not None else win_prob
            self.last_smoothed_prob = win_prob
            self.last_calibrated_prob = win_prob
            self.last_calibrated_combined = win_prob
            self.last_calibrated_phase = win_prob
            self.last_calibrated_per_over = win_prob
            self.last_calibrated_phase_target = win_prob
            
            return float(win_prob)
            
        except Exception as e:
            logger.warning(f"Reduced-over prediction failed: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _run_prediction(self) -> Optional[float]:
        """Run the prediction model on current match state.
        
        For reduced-over matches (total_overs < 20), uses MC-only mode
        instead of the trained XGBLogRegEnsemble model.
        """
        try:
            self._last_terminal_clamp = None

            # First check if match has a definitive result
            final_result = self._check_match_result()
            if final_result is not None:
                self.last_candidate_prob = None
                state = self.match_state
                reason = "chase_complete" if final_result == 1.0 else "innings_complete"
                if state.is_second_innings and state.wickets >= 10 and state.total_runs < (state.target or 0):
                    reason = "all_out"
                elif state.is_second_innings and state.overs >= float(self.format_config.total_overs):
                    reason = "no_balls_remaining"
                overs_int = int(state.overs)
                balls_part = int(round((state.overs - overs_int) * 10))
                balls_bowled = self._balls_bowled_from_overs(state.overs)
                self._last_terminal_clamp = {
                    "applied": True,
                    "reason": reason,
                    "probability": float(final_result),
                    "runs_needed": int(max(0, (state.target or 0) - state.total_runs)),
                    "balls_remaining": int(max(0, self.format_config.total_balls - balls_bowled)),
                    "wickets_lost": int(state.wickets),
                }
                return final_result
            
            # Apply CLI revised_target override for 2nd innings
            if self._cli_revised_target and self.match_state.is_second_innings:
                self.match_state.target = self._cli_revised_target
            
            # MC-only mode: reduced overs or explicit --mc-only flag
            effective_overs = self._effective_total_overs or self.format_config.total_overs
            if effective_overs < 20 or self.mc_only:
                self.last_candidate_prob = None
                return self._run_reduced_over_prediction()
            
            from bbl_pipeline.inference.schema import MatchState as PredictorMatchState
            
            # Parse overs into over and ball
            overs_float = self.match_state.overs
            over = int(overs_float)
            ball = int(round((overs_float - over) * 10))  # 12.3 -> 3 balls
            if ball >= self.format_config.balls_per_over:  # Handle edge case
                ball = 0
            
            # Build MatchState for predictor using its schema
            # Keep venue blank if it was not extracted. The feature store can then fall back
            # to CREX live venue stats directly without fuzzy-matching a generic placeholder.
            venue_name = (self.match_state.venue or "").strip()
                
            pred_state_kwargs = {
                "match_id": "live_match",  # Required field
                "venue": venue_name,
                "batting_team": self.match_state.batting_team,
                "bowling_team": self.match_state.bowling_team,
                "innings": 2 if self.match_state.is_second_innings else 1,
                "over": over,
                "ball": ball,
                "current_score": self.match_state.total_runs,
                "wickets_lost": self.match_state.wickets,
                "batsman_1": self.match_state.batsman1_name or "Unknown",
                "batsman_2": self.match_state.batsman2_name or "Unknown",
                "bowler": self.match_state.bowler1_name or "Unknown",
                "target_runs": self.match_state.target,
                "first_innings_score": self.match_state.target - 1 if self.match_state.target else None,
                "total_overs": self.format_config.total_overs,
                "balls_per_over": self.format_config.balls_per_over,
                "toss_winner": self._resolve_toss_winner_full_name() or None,
                "toss_decision": self.match_state.toss_decision or None,
                **self._compute_inn1_carryover_stats(),
            }
            supported_fields = set(getattr(PredictorMatchState, "__dataclass_fields__", {}).keys())
            if supported_fields:
                pred_state_kwargs = {
                    key: value for key, value in pred_state_kwargs.items() if key in supported_fields
                }
            pred_state = PredictorMatchState(**pred_state_kwargs)
            
            # Convert ball history to mapper format for rolling stats
            ball_history = self._build_ball_history_for_mapper()

            # If CREX gave sparse ball history, try betx21 recordings for richer data
            total_balls_bowled = self._balls_bowled_from_overs(self.match_state.overs)
            if total_balls_bowled > 0:
                completeness = len(ball_history) / total_balls_bowled
                if completeness < 0.3:
                    ball_history = self._try_betx21_backfill(ball_history)

            logger.info(f"Ball history has {len(ball_history)} balls, current state: {self.match_state.total_runs}/{self.match_state.wickets}")
            
            # Log ball history details for debugging
            if ball_history:
                logger.info(f"Ball history details: {ball_history[-3:]}")  # Last 3 balls
                # Show all wicket balls
                wicket_balls = [b for b in ball_history if b.get('is_wicket', 0) == 1]
                logger.info(f"Wicket balls in history ({len(wicket_balls)}): {wicket_balls}")
            
            # Get prediction using predictor (always show debug for visibility)
            win_prob = self.predictor.predict(
                pred_state, 
                debug=True,  # Always show debug output
                ball_history=ball_history
            )

            # The ODI model was trained with match-specific PP/death carryover
            # features. Do not expose an ML probability as primary when only a
            # summary (for example wickets) was recovered after restart.
            required_inn1_stats = ("inn1_wickets_lost", "inn1_pp_runs", "inn1_death_rr")
            carryover = self._inn1_cached_stats
            missing_carryover = [key for key in required_inn1_stats if key not in carryover]
            if pred_state.innings == 2 and missing_carryover:
                mc_result = self._run_monte_carlo_simulation(model_prob=None, use_ml_model=False)
                if mc_result and mc_result.get("available"):
                    ml_prob = float(win_prob)
                    win_prob = float(mc_result["simulation_6ball"]["mean_prob"])
                    self._prediction_guard = {
                        "applied": True,
                        "mode": "mc_fallback",
                        "reason": "incomplete_inn1_carryover",
                        "missing_features": missing_carryover,
                        "ml_probability_shadow": ml_prob,
                    }
                    logger.warning(
                        "ODI ML guarded: missing first-innings features %s; using MC primary %.4f",
                        missing_carryover,
                        win_prob,
                    )
                else:
                    self._prediction_guard = {
                        "applied": False,
                        "mode": "ml_unverified",
                        "reason": "incomplete_inn1_carryover_and_mc_unavailable",
                        "missing_features": missing_carryover,
                    }
            else:
                self._prediction_guard = None
            
            # Store the detailed probabilities for JSON output
            self.last_raw_prob = getattr(self.predictor, 'last_raw_prob', win_prob)
            self.last_smoothed_prob = getattr(self.predictor, 'last_smoothed_prob', win_prob)
            self.last_calibrated_prob = getattr(self.predictor, 'last_calibrated_prob', win_prob)
            self.last_calibrated_combined = getattr(self.predictor, 'last_calibrated_combined', win_prob)
            self.last_calibrated_phase = getattr(self.predictor, 'last_calibrated_phase', win_prob)
            self.last_calibrated_per_over = getattr(self.predictor, 'last_calibrated_per_over', win_prob)
            self.last_calibrated_phase_target = getattr(self.predictor, 'last_calibrated_phase_target', win_prob)
            self._last_terminal_clamp = getattr(self.predictor, 'last_terminal_clamp', None)
            self.last_shadow_prob = getattr(self.predictor, 'last_shadow_prob', win_prob)
            if self._prediction_guard and self._prediction_guard.get("applied"):
                # Keep raw ML diagnostics above, but make all displayed
                # calibrated probability fields agree with the MC primary.
                self.last_smoothed_prob = win_prob
                self.last_calibrated_prob = win_prob
                self.last_calibrated_combined = win_prob
                self.last_calibrated_phase = win_prob
                self.last_calibrated_per_over = win_prob
                self.last_calibrated_phase_target = win_prob
                self._last_ensemble_source = "mc_fallback"

            # Log shadow vs production when they differ (segment-specific T in shadow mode)
            if self.last_shadow_prob is not None and abs(self.last_shadow_prob - win_prob) > 0.002:
                over_1b = pred_state.over + 1
                print(f"[SHADOW] T=0.75 prod={win_prob:.1%} | seg-T shadow={self.last_shadow_prob:.1%} | inn={pred_state.innings} ov={over_1b}")

            # Candidate scoring is deliberately after incumbent guards and
            # never replaces the live probability. Both models receive the
            # same PredictorMatchState and ball-history snapshot.
            self.last_candidate_prob = self._run_candidate_shadow(pred_state, ball_history)

            return float(win_prob)
            
        except Exception as e:
            print(f"[WARN] Prediction error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _resolve_toss_winner_full_name(self) -> str:
        """Resolve CREX toss abbreviation (e.g. 'GT') to full team name using toss_decision.
        
        In inn1: toss chose 'bat' → they are batting_team; 'bowl' → bowling_team.
        In inn2: teams swap, so logic reverses.
        """
        abbr = self.match_state.toss_winner
        if not abbr:
            return ""
        bat = self.match_state.batting_team or ""
        bowl = self.match_state.bowling_team or ""
        # If already a full name, return as-is
        if abbr == bat or abbr == bowl:
            return abbr
        decision = (self.match_state.toss_decision or "").lower()
        if not decision or not bat:
            return abbr
        if self.match_state.is_second_innings:
            # Inn2: batting now = bowled inn1, bowling now = batted inn1
            return bowl if decision == "bat" else bat
        else:
            # Inn1: batting now = chose to bat, bowling now = chose to bowl
            return bat if decision == "bat" else bowl

    def _get_carryover_scraped_fields(self) -> dict:
        """Return toss + inn1 carryover fields for scraped_data dicts used in feature snapshots."""
        fields: dict = {}
        toss_full = self._resolve_toss_winner_full_name()
        if toss_full:
            fields['toss_winner'] = toss_full
        if self.match_state.toss_decision:
            fields['toss_decision'] = self.match_state.toss_decision
        if self.match_state.target:
            fields['first_innings_score'] = self.match_state.target - 1
        carryover = self._compute_inn1_carryover_stats()
        fields.update(carryover)
        return fields

    def _compute_inn1_carryover_stats(self) -> dict:
        """Compute innings 1 carryover stats from ball history for v6+ features.
        
        Returns dict with inn1_wickets_lost, inn1_pp_runs, inn1_death_rr 
        suitable for unpacking into PredictorMatchState kwargs.
        
        Strategy:
        1. During inn1: continuously cache stats from live ball data
        2. During inn2: try ball history first, fall back to cached stats
        """
        result = {}
        
        if not self.match_state.is_second_innings:
            # Still in inn1 — cache current stats from ball history for later use
            self._cache_inn1_stats_from_balls()
            return result
        
        # Inn2: try computing from ball history (has inn1 balls)
        balls = list(self.match_state.balls_data)
        if balls:
            # Find innings boundary (same logic as _build_ball_history_for_mapper)
            innings_start_idx = 0
            for i, ball in enumerate(balls):
                if i > 0:
                    prev_ball = balls[i - 1]
                    if prev_ball.over_number >= 15 and ball.over_number <= 5:
                        innings_start_idx = i
                        break
            
            inn1_balls = balls[:innings_start_idx] if innings_start_idx > 0 else []
            if inn1_balls:
                inn1_wickets = sum(1 for b in inn1_balls if b.is_wicket)
                result['inn1_wickets_lost'] = inn1_wickets
                
                pp_runs = sum(b.runs for b in inn1_balls if b.over_number < 6)
                result['inn1_pp_runs'] = float(pp_runs)
                result['inn1_pp_wickets'] = sum(
                    1 for b in inn1_balls if b.over_number < 6 and b.is_wicket
                )

                death_balls = [b for b in inn1_balls if b.over_number >= 15]
                if death_balls:
                    death_runs = sum(b.runs for b in death_balls)
                    result['inn1_death_rr'] = (death_runs / len(death_balls)) * self.format_config.balls_per_over
                    result['inn1_death_wickets'] = sum(1 for b in death_balls if b.is_wicket)
                result.update(self._compute_v14_pitch_features(inn1_balls, result))
                
                # Update cache with computed values
                self._inn1_cached_stats.update(result)
                self._inn1_stats_source = "ball_history"
                logger.info(f"Inn1 carryover from ball history: {result}")
                return result
        
        # Fallback 1: use cached stats from when inn1 was live
        if self._inn1_cached_stats:
            result.update(self._inn1_cached_stats)
            self._inn1_stats_source = self._inn1_cached_stats.get("inn1_stats_source", "cache")
            logger.info(f"Inn1 carryover from cache: {result}")
            return result

        # A restarted predictor may have no ball history, while the current
        # CREX page still exposes the completed first-innings summary.
        if self._inn1_page_stats:
            result.update(self._inn1_page_stats)
            self._inn1_cached_stats.update(result)
            self._inn1_stats_source = "crex_summary"
            logger.info(f"Inn1 carryover from CREX innings summary: {result}")
            return result
        
        # Fallback 2: try betx21 production recordings
        betx21_stats = self._fetch_inn1_stats_from_betx21()
        if betx21_stats:
            self._inn1_cached_stats.update(betx21_stats)  # Cache for subsequent calls
            result.update(betx21_stats)
            self._inn1_stats_source = "betx21"
            logger.info(f"Inn1 carryover from betx21: {result}")
            return result

        # Fallback 3: reconstruct from match states parquet (recorded during inn1 live monitoring)
        parquet_stats = self._load_inn1_stats_from_parquet()
        if parquet_stats:
            # Augment with v14 pitch features computed from recovered stats
            parquet_stats.update(self._compute_v14_pitch_features([], parquet_stats))
            self._inn1_cached_stats.update(parquet_stats)
            result.update(parquet_stats)
            self._inn1_stats_source = "parquet"
            logger.info(f"Inn1 carryover from match states parquet: {result}")
            return result

        logger.warning("No inn1 ball history, cache, betx21, or parquet data — using defaults")
        return result

    def _capture_first_innings_summary(self, page_text: str) -> None:
        """Recover first-innings wickets from current CREX summary text.

        CREX has used both ``233-10 ((44.0))`` and ``233/10 (44.0)``
        representations. We select the longest completed innings summary,
        which avoids mistaking the early second-innings score for innings one.
        """
        if not self.match_state.is_second_innings or not page_text:
            return

        patterns = (
            r"(?<!\d)(\d{1,3})\s*/\s*(\d{1,2})\s*\(?\s*\(?\s*(\d{1,2}(?:\.\d+)?)\s*\)?\s*\)?",
            r"(?<!\d)(\d{1,3})\s*-\s*(\d{1,2})\s*\(\(\s*(\d{1,2}(?:\.\d+)?)\s*\)\)",
        )
        candidates = []
        for pattern in patterns:
            for match in re.finditer(pattern, page_text):
                runs, wickets, overs = int(match.group(1)), int(match.group(2)), float(match.group(3))
                if 0 <= wickets <= 10 and 0 < overs <= 50 and runs >= 0:
                    candidates.append((overs, runs, wickets))

        if not candidates:
            return

        overs, runs, wickets = max(candidates)
        target_score = self.match_state.target
        if target_score is not None and runs + 1 != int(target_score):
            return
        self._inn1_page_stats = {
            "inn1_wickets_lost": wickets,
            "inn1_summary_score": runs,
            "inn1_summary_overs": overs,
            "inn1_stats_source": "crex_summary",
        }

    async def _hydrate_inn1_from_crex_over_api(self) -> None:
        """Recover full first-innings phase stats from CREX over summaries.

        CREX labels the first innings as ``0`` and the chase as ``1`` in its
        commentary feed. The visible page often contains only the latest ten
        balls, so query each first-innings over once after a restart.
        """
        if self._crex_inn1_api_attempted or not self.match_state.is_second_innings:
            return
        self._crex_inn1_api_attempted = True

        match_key_match = re.search(r"match-updates-([^/?#]+)", self.match_url or "")
        if not match_key_match:
            return
        match_key = match_key_match.group(1)

        try:
            summaries = []
            effective_overs = int(self._effective_total_overs or self.format_config.total_overs or 20)
            for over_number in range(min(max(effective_overs, 1), 50)):
                response = await self.page.request.post(
                    "https://content.crickapi.com/commentary/v3/getBallFeeds",
                    data={
                        "matchKey": match_key,
                        "lastDocId": "",
                        "filters": {"inning": 0, "overNumber": over_number},
                    },
                    headers={"Origin": "https://crex.com", "Referer": "https://crex.com/"},
                    timeout=15_000,
                )
                if not response.ok:
                    continue
                payload = await response.json()
                summaries.extend(item for item in (payload or []) if item.get("type") == "o")

            summaries.sort(key=lambda item: int(item.get("on", -1)))
            if not summaries:
                return

            # Avoid accepting a feed for another match or innings.
            if self.match_state.target is not None:
                final_score = str(summaries[-1].get("s", ""))
                score_match = re.match(r"(\d+)\s*/\s*(\d+)", final_score)
                if not score_match or int(score_match.group(1)) + 1 != int(self.match_state.target):
                    return

            pp_runs = sum(float(item.get("runs", 0) or 0) for item in summaries if int(item.get("on", -1)) <= 5)
            def score_wickets(item: dict) -> int:
                match = re.match(r"\d+\s*/\s*(\d+)", str(item.get("s", "")))
                return int(match.group(1)) if match else 0

            pp_summaries = [item for item in summaries if int(item.get("on", -1)) <= 5]
            mid_summaries = [item for item in summaries if int(item.get("on", -1)) <= 15]
            pp_wickets = score_wickets(pp_summaries[-1]) if pp_summaries else 0
            death_items = [item for item in summaries if int(item.get("on", -1)) > 15]
            death_runs = sum(float(item.get("runs", 0) or 0) for item in death_items)
            final_wickets = score_wickets(summaries[-1])
            wickets_at_end_of_setup = score_wickets(mid_summaries[-1]) if mid_summaries else 0
            death_wickets = max(0, final_wickets - wickets_at_end_of_setup)
            death_rr = (death_runs / len(death_items)) if death_items else None

            final_score = str(summaries[-1].get("s", ""))
            score_match = re.match(r"(\d+)\s*/\s*(\d+)", final_score)
            if not score_match:
                return

            stats = {
                "inn1_wickets_lost": int(score_match.group(2)),
                "inn1_pp_runs": pp_runs,
                "inn1_pp_wickets": pp_wickets,
                "inn1_death_rr": death_rr if death_rr is not None else 9.0,
                "inn1_death_wickets": death_wickets,
                "inn1_stats_source": "crex_over_api",
            }
            stats.update(self._compute_v14_pitch_features([], stats))
            self._inn1_page_stats.update(stats)
            self._inn1_cached_stats.update(stats)
            self._inn1_stats_source = "crex_over_api"
            logger.info(f"Inn1 carryover from CREX over API: {stats}")
        except Exception as exc:
            logger.warning(f"CREX first-innings over API unavailable: {exc}")

    def _cache_inn1_stats_from_balls(self):
        """Cache inn1 stats from current ball data (called during inn1)."""
        balls = list(self.match_state.balls_data)
        if not balls:
            return
        
        wickets = sum(1 for b in balls if b.is_wicket)
        self._inn1_cached_stats['inn1_wickets_lost'] = wickets
        
        pp_runs = sum(b.runs for b in balls if b.over_number < 6)
        if any(b.over_number < 6 for b in balls):
            self._inn1_cached_stats['inn1_pp_runs'] = float(pp_runs)
            self._inn1_cached_stats['inn1_pp_wickets'] = sum(
                1 for b in balls if b.over_number < 6 and b.is_wicket
            )

        death_balls = [b for b in balls if b.over_number >= 15]
        if death_balls:
            death_runs = sum(b.runs for b in death_balls)
            self._inn1_cached_stats['inn1_death_rr'] = (death_runs / len(death_balls)) * self.format_config.balls_per_over
            self._inn1_cached_stats['inn1_death_wickets'] = sum(1 for b in death_balls if b.is_wicket)
        self._inn1_cached_stats.update(
            self._compute_v14_pitch_features(balls, self._inn1_cached_stats)
        )

    def _venue_pitch_key(self) -> str:
        venue = self.match_state.venue
        if not venue or str(venue).strip().lower() in {"unknown", "not available"}:
            venue = self.venue_override or ""
        return venue.split(",")[0].strip() if venue else "Unknown"

    def _load_venue_pitch_baselines(self) -> dict:
        if self._venue_pitch_baselines is not None:
            return self._venue_pitch_baselines
        self._venue_pitch_baselines = {}
        try:
            path = Path(self.model_dir) / "venue_pitch_baselines.json"
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    self._venue_pitch_baselines = json.load(f)
        except Exception as exc:
            logger.debug(f"Could not load venue pitch baselines: {exc}")
            self._venue_pitch_baselines = {}
        return self._venue_pitch_baselines

    @staticmethod
    def _average_boundary_pct_last_18(balls: list[BallData]) -> Optional[float]:
        if not balls:
            return None
        vals = []
        for idx in range(len(balls)):
            window = balls[max(0, idx - 17): idx + 1]
            vals.append(sum(1 for b in window if b.is_boundary) / len(window))
        return float(sum(vals) / len(vals)) if vals else None

    def _compute_v14_pitch_features(self, inn1_balls: list[BallData], stats: dict) -> dict:
        """Compute v14 live pitch-relative features from inn1 carryover data."""
        baselines = self._load_venue_pitch_baselines()
        global_base = baselines.get("global", {}) if isinstance(baselines, dict) else {}
        venue_base = {}
        if isinstance(baselines, dict):
            venue_base = baselines.get("venues", {}).get(self._venue_pitch_key(), {})

        def base(name: str, default: float) -> float:
            value = venue_base.get(name, global_base.get(name, default))
            try:
                return float(value)
            except (TypeError, ValueError):
                return default

        out = {}
        if "inn1_pp_runs" in stats:
            out["pp_score_vs_venue"] = float(stats["inn1_pp_runs"]) - base("venue_pp_avg", 45.0)
        if "inn1_pp_wickets" in stats:
            out["pp_wkts_vs_venue"] = float(stats["inn1_pp_wickets"]) - base("venue_pp_wickets_avg", 1.3)
        if "inn1_death_rr" in stats:
            out["death_rr_vs_venue"] = float(stats["inn1_death_rr"]) - base("venue_death_rr_avg", 10.0)
        if "inn1_death_wickets" in stats:
            out["death_wkts_vs_venue"] = float(stats["inn1_death_wickets"]) - base("venue_death_wickets_avg", 2.5)

        if inn1_balls:
            avg_boundary18 = self._average_boundary_pct_last_18(inn1_balls)
            mid_balls = [b for b in inn1_balls if 6 <= b.over_number <= 14]
            mid_avg_boundary18 = self._average_boundary_pct_last_18(mid_balls)
            if avg_boundary18 is not None:
                out["avg_boundary18_vs_venue"] = avg_boundary18 - base("venue_avg_boundary18", 0.18)
            if mid_avg_boundary18 is not None:
                out["mid_avg_boundary18_vs_venue"] = (
                    mid_avg_boundary18 - base("venue_mid_avg_boundary18", 0.18)
                )
        return out

    def _fetch_inn1_stats_from_betx21(self) -> dict:
        """Fallback: fetch inn1 stats from betx21 production score recordings.
        
        Uses SSH+SCP to download the scores file, then reconstructs inn1 stats
        from score progression data. Only called when both ball history and cache
        are empty (e.g., predictor started mid-inn2).
        
        Returns dict with inn1_pp_runs, inn1_death_rr, inn1_wickets_lost or empty dict.
        """
        try:
            # scripts/ is at project root, one level above src/
            project_root = str(Path(__file__).resolve().parents[3])
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
            from scripts.fetch_betx21_inn1_stats import (
                auto_detect_match_id, download_scores, load_scores, extract_inn1_stats
            )
        except ImportError:
            logger.debug("betx21 fetch script not available")
            return {}
        
        try:
            today = datetime.utcnow().strftime("%Y-%m-%d")
            
            # In inn2 batting_team is the chaser, bowling_team is the defender
            # Use both so token matching works regardless of who batted first
            batting_team = self.match_state.batting_team or ""
            bowling_team = self.match_state.bowling_team or ""
            if not batting_team:
                return {}
            
            logger.info(f"Trying betx21 fallback for {batting_team} vs {bowling_team}")
            # Use token-overlap matching (handles abbreviated names like "R C Bengaluru")
            match_id = auto_detect_match_id(today, batting_team, bowling_team)
            
            if not match_id:
                logger.debug(f"No betx21 match found for {batting_team} vs {bowling_team}")
                return {}
            
            path = download_scores(match_id, today)
            if not path:
                return {}
            
            lines = load_scores(path)
            stats = extract_inn1_stats(lines)
            
            if stats.get("data_quality") in ("full", "partial"):
                result = {}
                if "inn1_pp_runs" in stats:
                    result["inn1_pp_runs"] = float(stats["inn1_pp_runs"])
                if "inn1_death_rr" in stats:
                    result["inn1_death_rr"] = float(stats["inn1_death_rr"])
                if "inn1_wickets_lost" in stats:
                    result["inn1_wickets_lost"] = int(stats["inn1_wickets_lost"])
                if "inn1_pp_wickets" in stats:
                    result["inn1_pp_wickets"] = int(stats["inn1_pp_wickets"])
                if "inn1_death_wickets" in stats:
                    result["inn1_death_wickets"] = int(stats["inn1_death_wickets"])
                result.update(self._compute_v14_pitch_features([], result))
                return result
            
            return {}
        except Exception as e:
            logger.warning(f"betx21 fallback failed: {e}")
            return {}

    def _load_inn1_stats_from_parquet(self) -> dict:
        """Reconstruct inn1 stats from match states parquet recorded during inn1.

        Filters today's Inn1 records then derives pp_runs, pp_wickets,
        wickets_lost, death_rr, death_wickets from the over-by-over progression.
        Returns empty dict if parquet unavailable or insufficient data.
        """
        try:
            if not self.states_dir:
                return {}
            parquet_path = Path(self.states_dir) / f"{self.match_id if hasattr(self, 'match_id') else self.match_url.split('/')[-2]}.parquet"
            if not parquet_path.exists():
                return {}

            import pandas as pd
            df = pd.read_parquet(parquet_path)
            if df.empty or "innings" not in df.columns or "total_runs" not in df.columns:
                return {}

            df["_ts"] = pd.to_datetime(df["timestamp"], errors="coerce")
            today_str = datetime.now().strftime("%Y-%m-%d")
            inn1 = df[
                (df["innings"] == 1.0) &
                (df["_ts"].dt.strftime("%Y-%m-%d") == today_str)
            ].copy()

            if len(inn1) < 5:
                logger.debug(f"Parquet Inn1 fallback: too few records ({len(inn1)}), skipping")
                return {}

            inn1 = inn1.sort_values("_ts")
            result = {}

            # PP stats: cumulative score at end of over 6
            pp_rows = inn1[inn1["over_number"] == 6]
            if not pp_rows.empty:
                pp_last = pp_rows.iloc[-1]
                result["inn1_pp_runs"] = float(pp_last.get("total_runs", 0))
                result["inn1_pp_wickets"] = int(pp_last.get("wickets", 0))

            # Final wickets and score
            final_row = inn1.iloc[-1]
            result["inn1_wickets_lost"] = int(final_row.get("wickets", 4))
            final_score = float(final_row.get("total_runs", 0))

            # Death RR: runs from end of over 15 to final
            death_start_rows = inn1[inn1["over_number"] == 15]
            if not death_start_rows.empty and final_score > 0:
                death_start_score = float(death_start_rows.iloc[-1].get("total_runs", 0))
                death_start_wkts = int(death_start_rows.iloc[-1].get("wickets", 0))
                death_runs = final_score - death_start_score
                death_window_balls = max(1, 5 * self.format_config.balls_per_over)
                result["inn1_death_rr"] = round((death_runs / death_window_balls) * self.format_config.balls_per_over, 2)
                result["inn1_death_wickets"] = int(final_row.get("wickets", 0)) - death_start_wkts

            logger.info(f"Parquet Inn1 fallback loaded: {result}")
            return result
        except Exception as e:
            logger.warning(f"Parquet Inn1 fallback failed: {e}")
            return {}

    def _build_ball_history_for_mapper(self) -> list:
        """
        Convert scraped ball data to the format expected by RealTimeFeatureMapper.
        The mapper expects dicts with: runs_scored, is_wicket, is_boundary, total_score, total_wickets
        """
        history = []
        running_score = 0
        running_wickets = 0
        
        # Get balls - use original order first to detect innings boundary
        balls = list(self.match_state.balls_data)
        
        # For 2nd innings: filter to only include balls from current innings
        if self.match_state.is_second_innings and balls:
            current_overs = self.match_state.overs
            
            # SPECIAL CASE: 2nd innings just started (0/0 at 0.0 overs)
            # No balls have been bowled yet - return empty history
            if current_overs == 0 and self.match_state.total_runs == 0:
                logger.info("2nd innings just started - returning empty ball history")
                return []
            
            innings_start_idx = 0
            
            # Detection: Find where overs reset (e.g., 19.4 -> 0.1), indicating innings change
            # Look for the point where overs jump backwards significantly
            for i, ball in enumerate(balls):
                if i > 0:
                    prev_ball = balls[i - 1]
                    # If previous ball was in high overs (late 1st innings) and this ball is in low overs
                    if prev_ball.over_number >= 15 and ball.over_number <= 5:
                        innings_start_idx = i
                        logger.info(f"Detected innings boundary at index {i}: over {prev_ball.over_number} -> {ball.over_number}")
                        break
            
            # Only keep balls from current innings
            if innings_start_idx > 0:
                balls = balls[innings_start_idx:]
                logger.info(f"Filtered ball history: keeping {len(balls)} balls from 2nd innings")
            else:
                # No innings boundary found - check if all balls are from 1st innings
                # If all balls have high over numbers and we're early in 2nd innings, clear history
                if balls and current_overs <= 2:
                    max_over_in_history = max(b.over_number for b in balls)
                    if max_over_in_history >= 15:
                        logger.info(f"2nd innings early but ball history shows 1st innings (max over {max_over_in_history}) - clearing")
                        balls = []
        
        # Now sort the filtered balls by over/ball
        sorted_balls = sorted(balls, key=lambda b: (b.over_number, b.ball_in_over))
        
        for ball in sorted_balls:
            running_score += ball.runs
            if ball.is_wicket:
                running_wickets += 1
            
            history.append({
                'innings_num': 2 if self.match_state.is_second_innings else 1,
                'over_number': ball.over_number,
                'ball_number': ball.ball_in_over,
                'runs_scored': ball.runs,
                'is_wicket': 1 if ball.is_wicket else 0,
                'is_boundary': 1 if ball.is_boundary or ball.is_six else 0,
                'total_score': running_score,
                'total_wickets': running_wickets,
            })
        
        # CRITICAL: Sync with actual match state if there's a mismatch
        # The scraped ball-by-ball data may miss some events
        actual_wickets = self.match_state.wickets
        actual_score = self.match_state.total_runs
        
        if history:
            # Always sync the totals to match reality
            history[-1]['total_score'] = actual_score
            history[-1]['total_wickets'] = actual_wickets
            
            # DON'T retroactively mark balls as wickets - this creates false rolling stats
            # If ball history is incomplete, accept that and let rolling stats reflect
            # only the wickets we actually have data for
            if running_wickets != actual_wickets or running_score != actual_score:
                logger.warning(
                    f"Ball history mismatch: running={running_score}/{running_wickets}, "
                    f"actual={actual_score}/{actual_wickets}. "
                    f"History has {len(history)} balls (may be incomplete from scraper)"
                )
        
        return history

    def _try_betx21_backfill(self, crex_history: list) -> list:
        """Try to backfill sparse CREX ball history with betx21 recordings.

        When CREX only provides a handful of balls on a mid-match restart, this
        method downloads today's betx21 scores file, reconstructs ball-by-ball
        data from the `b` arrays, and returns the richer history.

        Falls back to the original crex_history on any error.
        """
        try:
            import sys as _sys
            from pathlib import Path as _Path
            _scripts = _Path(__file__).resolve().parents[3] / "scripts"
            if str(_scripts) not in _sys.path:
                _sys.path.insert(0, str(_scripts))

            from fetch_betx21_inn1_stats import (
                auto_detect_match_id,
                download_scores,
                load_scores,
                extract_ball_history,
            )
            from datetime import datetime as _dt

            innings_num = 2 if self.match_state.is_second_innings else 1
            batting_team = self.match_state.batting_team or ""
            bowling_team = self.match_state.bowling_team or ""

            # Try today first, then yesterday as fallback
            for date_offset in (0, -1):
                import datetime as _datetime
                date_str = (_dt.utcnow() + _datetime.timedelta(days=date_offset)).strftime("%Y-%m-%d")
                match_id = auto_detect_match_id(date_str, batting_team, bowling_team)
                if match_id:
                    break
            else:
                logger.warning("betx21 backfill: no matching match found", batting=batting_team, bowling=bowling_team)
                return crex_history

            scores_path = download_scores(match_id, date_str)
            if not scores_path:
                logger.warning("betx21 backfill: failed to download scores", match_id=match_id)
                return crex_history

            ticks = load_scores(scores_path)
            bx_history = extract_ball_history(ticks, innings_num=innings_num)

            if not bx_history:
                logger.warning("betx21 backfill: extracted 0 balls", match_id=match_id)
                return crex_history

            # Only use betx21 data when it's actually richer than CREX
            if len(bx_history) > len(crex_history):
                logger.info(
                    "betx21 backfill: using richer history",
                    betx21_balls=len(bx_history),
                    crex_balls=len(crex_history),
                    match_id=match_id,
                )
                return bx_history

        except Exception as exc:
            logger.warning("betx21 backfill failed", error=str(exc))

        return crex_history

    def _build_features(self) -> Optional[Dict[str, Any]]:
        """Build feature dictionary from match state for model input."""
        try:
            # Calculate derived features
            total_balls = self._balls_bowled_from_overs(self.match_state.overs)
            balls_remaining = self.format_config.total_balls - total_balls
            
            # Determine phase from format config thresholds
            overs_bowled = self.match_state.overs
            thresholds = self.format_config.phase_thresholds
            if overs_bowled <= thresholds.get('powerplay', 6):
                phase = 1  # Powerplay
            elif overs_bowled <= thresholds.get('middle', 15):
                phase = 2  # Middle overs
            elif len(thresholds) > 3 and overs_bowled <= thresholds.get('setup', thresholds.get('middle', 15)):
                phase = 3  # Setup overs (ODI only)
            else:
                phase = len(thresholds)  # Death overs
            
            features = {
                'total_runs': self.match_state.total_runs,
                'wickets': self.match_state.wickets,
                'overs': self.match_state.overs,
                'balls_remaining': balls_remaining,
                'current_run_rate': self.match_state.current_run_rate,
                'required_run_rate': self.match_state.required_run_rate,
                'phase': phase,
                'is_second_innings': int(self.match_state.is_second_innings),
                'batsman1_runs': self.match_state.batsman1_runs,
                'batsman1_balls': self.match_state.batsman1_balls,
                'batsman1_sr': (self.match_state.batsman1_runs / self.match_state.batsman1_balls * 100) if self.match_state.batsman1_balls > 0 else 0,
                'batsman2_runs': self.match_state.batsman2_runs,
                'batsman2_balls': self.match_state.batsman2_balls,
                'batsman2_sr': (self.match_state.batsman2_runs / self.match_state.batsman2_balls * 100) if self.match_state.batsman2_balls > 0 else 0,
                'bowler1_overs': self.match_state.bowler1_overs,
                'bowler1_runs': self.match_state.bowler1_runs,
                'bowler1_wickets': self.match_state.bowler1_wickets,
                'bowler1_economy': (self.match_state.bowler1_runs / self.match_state.bowler1_overs) if self.match_state.bowler1_overs > 0 else 0,
            }
            
            # Add target-related features for 2nd innings
            if self.match_state.is_second_innings and self.match_state.target:
                features['target'] = self.match_state.target
                features['runs_required'] = self.match_state.target - self.match_state.total_runs
                features['required_run_rate'] = (
                    features['runs_required'] / (balls_remaining / self.format_config.balls_per_over)
                    if balls_remaining > 0 else 0
                )
            
            return features
            
        except Exception as e:
            print(f"[WARN] Error building features: {e}")
            return None
    
    async def run(self, poll_interval: float = 2.0):
        """Run the live predictor continuously."""
        self._running = True
        
        started = await self.start()
        if not started:
            print("[ERROR] Failed to start predictor")
            return
        
        print("\n" + "="*60)
        print("LIVE MATCH PREDICTION")
        print("="*60)
        print(f"   {self.match_state.batting_team} vs {self.match_state.bowling_team}")
        if self.match_state.venue:
            print(f"   Venue: {self.match_state.venue}")
        print("="*60)
        print("\n[...] Monitoring match... Press Ctrl+C to stop\n")
        
        try:
            while self._running:
                # Poll and predict
                win_prob = await self.poll_and_predict()
                
                # Display current state
                self._display_state(win_prob)
                
                await asyncio.sleep(poll_interval)
                
        except asyncio.CancelledError:
            print("\n[STOP] Predictor stopped")
        except KeyboardInterrupt:
            print("\n[STOP] Stopped by user")
        finally:
            # Finalize match state recording if enabled
            if self.match_state_logger:
                try:
                    # Only the second innings result settles the match. An
                    # innings-1 boundary must remain resumable and must not
                    # create a completed metadata row with a false winner.
                    final_result = self._check_match_result()
                    match_complete = final_result is not None
                    
                    if match_complete:
                        # Match is finished - finalize with result
                        print("[RECORD] Match complete - finalizing recording")
                        state = self.match_state
                        winner = state.batting_team if final_result == 1.0 else state.bowling_team
                        self.match_state_logger.finalize(
                            winner=winner,
                            result_type="completed",
                            match_url=self.match_url,
                        )
                    else:
                        # Match interrupted mid-play - DON'T call finalize()
                        # This allows recording to resume if predictor restarts
                        # Just flush any remaining buffer
                        self.match_state_logger.flush()
                        state = self.match_state
                        print(f"[RECORD] Recording paused at {state.batting_team}: {state.total_runs}/{state.wickets} ({state.overs} overs)")
                        print("[RECORD] ⚠️  Match incomplete - recording NOT finalized (allows resume)")
                    
                except Exception as e:
                    print(f"[WARN] Logger finalize/flush failed: {e}")
            await self.stop()
    
    def _build_live_feature_snapshot(self) -> tuple:
        """Build the current predictor feature snapshot for JSON/debug/ODM use."""
        over = int(self.match_state.overs)
        ball = int(round((self.match_state.overs - over) * 10))
        if ball >= 6:
            ball = 0

        if not self.predictor:
            return over, ball, {}

        try:
            scraped_data = {
                'innings_num': 2 if self.match_state.is_second_innings else 1,
                'over_number': over,
                'ball_number': ball,
                'total_score': self.match_state.total_runs,
                'total_wickets': self.match_state.wickets,
                'batsman1_name': self.match_state.batsman1_name,
                'batsman2_name': self.match_state.batsman2_name,
                'bowler1_name': self.match_state.bowler1_name,
                'current_batsman': self.match_state.batsman1_name,
                'non_striker': self.match_state.batsman2_name,
                'batsman1_balls': self.match_state.batsman1_balls,
                'batsman2_balls': self.match_state.batsman2_balls,
                'batting_team': self.match_state.batting_team,
                'bowling_team': self.match_state.bowling_team,
                'venue': self.match_state.venue,
                'target_score': self.match_state.target,
                'runs_needed': (self.match_state.target - self.match_state.total_runs) if self.match_state.target else 0,
                **self._get_carryover_scraped_fields(),
            }
            feat_df = self.predictor.feature_mapper.create_feature_dataframe(scraped_data)
            feat_df = self._engineer_live_feature_dataframe(feat_df, scraped_data["innings_num"])
            features = {
                key: (float(value) if isinstance(value, (int, float)) else value)
                for key, value in feat_df.iloc[0].to_dict().items()
            }
            return over, ball, features
        except Exception as e:
            logger.warning(f"Could not build live feature snapshot: {e}")
            return over, ball, {}

    @staticmethod
    def _engineer_live_feature_dataframe(feat_df, innings_num: int):
        """Apply the same inn2 engineering used by the phase router to live exports."""
        if int(innings_num) != 2:
            return feat_df
        try:
            from bbl_pipeline.features.inn2_engineering import engineer_inn2_features

            return engineer_inn2_features(feat_df)
        except Exception as exc:
            logger.warning(f"Could not engineer innings-2 live features: {exc}")
            return feat_df

    def _update_odm_prediction(
        self,
        features: Dict[str, Any],
        over: int,
        ball: int,
        current_ml_prob: Optional[float] = None,
    ) -> None:
        """Update ODM advisory output from current ML probability and distinct-ball history."""
        if not self.odm_model_dir:
            self.last_odm_prediction = {
                'status': 'unavailable',
                'reason': 'ODM model not configured.',
            }
            return

        if not self.predictor:
            self.last_odm_prediction = {
                'status': 'unavailable',
                'reason': 'ODM advisory requires the main ML predictor to be active.',
            }
            return

        if not features:
            self.last_odm_prediction = {
                'status': 'unavailable',
                'reason': 'Live ODM features are unavailable for the current state.',
            }
            return

        try:
            self.last_odm_prediction = self.odm_model.predict(
                live_features=features,
                predictor=self.predictor,
                batting_team=self.match_state.batting_team,
                bowling_team=self.match_state.bowling_team,
                venue=self.match_state.venue or "Unknown",
                league=self.league,
                innings=2 if self.match_state.is_second_innings else 1,
                over=over,
                ball=ball,
                target_score=self.match_state.target,
                current_ml_prob=current_ml_prob if current_ml_prob is not None else getattr(self, 'last_raw_prob', None),
                history=self._prediction_history,
            )
        except Exception as e:
            logger.warning(f"ODM advisory update failed: {e}")
            self.last_odm_prediction = {
                'status': 'error',
                'reason': str(e),
            }

    def _display_state(self, win_prob: Optional[float]):
        """Display current match state and prediction."""
        state = self.match_state
        
        # Build display line
        display = f"\r{state.batting_team}: {state.total_runs}/{state.wickets} ({state.overs} ov)"
        
        if state.is_second_innings and state.target:
            runs_needed = state.target - state.total_runs
            display += f" | Need: {runs_needed}"
        else:
            display += f" | CRR: {state.current_run_rate}"
        
        if win_prob is not None:
            bar_len = 20
            filled = int(win_prob * bar_len)
            bar = "#" * filled + "-" * (bar_len - filled)
            # Show both teams' probabilities
            bowling_prob = 1 - win_prob
            display += f" | {state.batting_team}: {win_prob*100:.1f}% [{bar}] {state.bowling_team}: {bowling_prob*100:.1f}%"

            # Ensemble blending with market odds
            market_batting_prob = self._get_market_batting_probability()
            market_age = self._market_age_seconds()
            self._last_market_age_seconds = market_age
            ensemble_alpha = getattr(self, 'ensemble_alpha', 0.7)
            ensemble_prob, ensemble_source = blend_predictions(
                model_prob=win_prob,
                market_prob=market_batting_prob,
                market_age_seconds=market_age,
                alpha=ensemble_alpha,
            )
            # Store for JSON / logger consumption
            self._last_ensemble_prob = ensemble_prob
            self._last_ensemble_source = ensemble_source
            self._last_ensemble_alpha = ensemble_alpha
            if self._prediction_guard and self._prediction_guard.get("applied"):
                self._last_ensemble_prob = win_prob
                self._last_ensemble_source = "mc_fallback"

            if ensemble_source == "ensemble":
                display += f" | Ens: {ensemble_prob*100:.1f}%"

            market_stack = self._compute_market_stack_overlay(win_prob, market_batting_prob)
            self._last_market_stack = market_stack
            if market_stack.get("status") == "ready":
                stack_bat_prob = float(market_stack["stack_bat_win_prob"])
                display += f" | Stack(dry): {stack_bat_prob*100:.1f}%"
            terminal_clamp = getattr(
                self,
                "_last_terminal_clamp",
                getattr(getattr(self, "predictor", None), "last_terminal_clamp", None),
            )
            self._last_terminal_clamp = terminal_clamp
            if terminal_clamp:
                display += f" | Clamp: {terminal_clamp.get('reason')}"

            over, ball, live_features = self._build_live_feature_snapshot()
            self._update_odm_prediction(live_features, over, ball, current_ml_prob=win_prob)
            if self.last_odm_prediction.get('status') == 'ready':
                odm_direction = str(self.last_odm_prediction.get('direction', '')).upper()
                odm_confidence = float(self.last_odm_prediction.get('direction_confidence', 0.0)) * 100.0
                display += f" | ODM {odm_direction} {odm_confidence:.0f}%"

            # Track prediction history
            self._prediction_history.append({
                "overs": state.overs,
                "bat_prob": win_prob,
                "bowl_prob": bowling_prob,
                # Keep the same model-derived score views as the current JSON
                # snapshot so public charts can show prediction movement over time.
                "expected_final_score": live_features.get("expected_final_score"),
                "projected_score": live_features.get("projected_score"),
                "score": state.total_runs,
                "wickets": state.wickets,
                "innings": 2 if state.is_second_innings else 1,
                "batting_team": state.batting_team,
                "bowling_team": state.bowling_team,
                "market_stack_bat_prob": (
                    market_stack.get("stack_bat_win_prob")
                    if market_stack.get("status") == "ready"
                    else None
                ),
                "terminal_clamp": terminal_clamp,
                "timestamp": datetime.now().isoformat()
            })
            
            # Persist history to file for page refresh resilience
            self._save_history()
            
            # Write to JSON if output file specified
            if self.output_json:
                self._write_json_state(win_prob)
            
            # Record ball state if logger is enabled
            if self.match_state_logger:
                try:
                    # Compute features for logger (same logic as _write_json_state)
                    over = int(state.overs)
                    ball = int(round((state.overs - over) * 10))
                    if ball >= 6:
                        ball = 0
                    
                    scraped_data = {
                        'innings_num': 2 if state.is_second_innings else 1,
                        'over_number': over,
                        'ball_number': ball,
                        'total_score': state.total_runs,
                        'total_wickets': state.wickets,
                        'batsman1_name': state.batsman1_name,
                        'batsman2_name': state.batsman2_name,
                        'bowler1_name': state.bowler1_name,
                        'bowler_data_source': state.bowler_data_source,
                        'current_batsman': state.batsman1_name,
                        'non_striker': state.batsman2_name,
                        'batsman1_balls': state.batsman1_balls,
                        'batsman2_balls': state.batsman2_balls,
                        'batting_team': state.batting_team,
                        'bowling_team': state.bowling_team,
                        'venue': state.venue,
                        'target_score': state.target,
                        'runs_needed': (state.target - state.total_runs) if state.target else 0,
                        **self._get_carryover_scraped_fields(),
                    }
                    
                    if self.predictor:
                        feat_df = self.predictor.feature_mapper.create_feature_dataframe(scraped_data)
                        feat_df = self._engineer_live_feature_dataframe(feat_df, scraped_data["innings_num"])
                        features = {
                            k: (float(v) if isinstance(v, (int, float)) else str(v))
                            for k, v in feat_df.iloc[0].to_dict().items()
                        }
                    else:
                        # MC-only matches still need an auditable state row;
                        # the reduced feature snapshot is preferable to a gap.
                        features = self._build_features() or {}
                    
                    # Assemble market odds dict
                    market_odds = {
                        "market_fav_team": state.market_fav_team,
                        "market_back_odds": state.market_back_odds,
                        "market_lay_odds": state.market_lay_odds,
                        "market_fav_prob": state.market_fav_prob,
                        "market_source": "crex_live_market" if state.market_fav_prob else "",
                        "market_age_seconds": self._last_market_age_seconds,
                        "market_unavailable_reason": (
                            "no_market_probability" if not state.market_fav_prob else ""
                        ),
                    }

                    inference_context = {
                        "source_state": scraped_data,
                        "model_input_features": getattr(self.predictor, "_last_full_feature_dict", {}) if self.predictor else {},
                        "feature_row": features,
                        "ball_history_tail": (self._build_ball_history_for_mapper() or [])[-30:],
                        "prediction_guard": getattr(self, "_prediction_guard", None),
                        "terminal_clamp": getattr(self, "_last_terminal_clamp", None),
                    }
                    
                    # Record ball
                    self.match_state_logger.record_ball(
                        match_state=state,
                        features_dict=features,
                        predictor=self.predictor,
                        market_odds=market_odds,
                        ensemble_prob=getattr(self, '_last_ensemble_prob', None),
                        ensemble_alpha=getattr(self, '_last_ensemble_alpha', None),
                        ensemble_source=getattr(self, '_last_ensemble_source', None),
                        candidate_prob=getattr(self, 'last_candidate_prob', None),
                        candidate_model_version=getattr(self, 'candidate_model_version', ''),
                        candidate_artifact_sha256=getattr(self, 'candidate_artifact_sha256', ''),
                        candidate_feature_order_sha256=getattr(self, 'candidate_feature_order_sha256', ''),
                        candidate_source_revision=getattr(self, 'candidate_source_revision', ''),
                        inference_context=inference_context,
                    )
                except Exception as e:
                    pass  # Logging errors are already handled in logger
        
        # Pad and print
        print(display.ljust(120), end="", flush=True)
    
    def _write_json_state(self, win_prob: float):
        """Write current state to JSON file for Streamlit."""
        try:
            state = self.match_state

            over = int(state.overs)
            ball = int(round((state.overs - over) * 10))
            if ball >= 6:
                ball = 0

            # Get features if predictor is available
            pred_state = None
            scraped_data = None
            ball_history = None
            features = {}
            if self.predictor:
                try:
                    from bbl_pipeline.inference.schema import MatchState as PredictorMatchState

                    pred_state = PredictorMatchState(
                        match_id="live_match",
                        venue=state.venue or "Unknown",
                        batting_team=state.batting_team,
                        bowling_team=state.bowling_team,
                        innings=2 if state.is_second_innings else 1,
                        over=over,
                        ball=ball,
                        current_score=state.total_runs,
                        wickets_lost=state.wickets,
                        batsman_1=state.batsman1_name or "Unknown",
                        batsman_2=state.batsman2_name or "Unknown",
                        bowler=state.bowler1_name or "Unknown",
                        target_runs=state.target,
                        batsman1_balls=state.batsman1_balls,
                        batsman2_balls=state.batsman2_balls,
                    )

                    scraped_data = {
                        'innings_num': pred_state.innings,
                        'over_number': over,
                        'ball_number': ball,
                        'total_score': state.total_runs,
                        'total_wickets': state.wickets,
                        'batsman1_name': state.batsman1_name,
                        'batsman2_name': state.batsman2_name,
                        'bowler1_name': state.bowler1_name,
                        'bowler_data_source': state.bowler_data_source,
                        'current_batsman': state.batsman1_name,
                        'non_striker': state.batsman2_name,
                        'batsman1_balls': state.batsman1_balls,
                        'batsman2_balls': state.batsman2_balls,
                        'batting_team': state.batting_team,
                        'bowling_team': state.bowling_team,
                        'venue': state.venue,
                        'target_score': state.target,
                        'runs_needed': (state.target - state.total_runs) if state.target else 0,
                        **self._get_carryover_scraped_fields(),
                    }
                    ball_history = self._build_ball_history_for_mapper()

                    feat_df = self.predictor.feature_mapper.create_feature_dataframe(scraped_data)
                    feat_df = self._engineer_live_feature_dataframe(feat_df, pred_state.innings)
                    features = {
                        k: (float(v) if isinstance(v, (int, float)) else str(v))
                        for k, v in feat_df.iloc[0].to_dict().items()
                    }
                except Exception:
                    pass
            
            output = {
                "timestamp": datetime.now().isoformat(),
                "match_url": self.match_url,
                "model_dir": self.model_dir,
                "feature_store_dir": self.feature_store_dir,
                "batting_team": state.batting_team,
                "bowling_team": state.bowling_team,
                "score": state.total_runs,
                "wickets": state.wickets,
                "overs": state.overs,
                "over": over,
                "ball": ball,
                "target": state.target,
                "target_runs": state.target,  # alias for external consumers
                "batsman1_name": state.batsman1_name,
                "batsman1_runs": state.batsman1_runs,
                "batsman1_balls": state.batsman1_balls,
                "batsman2_name": state.batsman2_name,
                "batsman2_runs": state.batsman2_runs,
                "batsman2_balls": state.batsman2_balls,
                "current_run_rate": state.current_run_rate,
                "required_run_rate": state.required_run_rate,
                "bat_win_prob": win_prob,
                "bowl_win_prob": 1 - win_prob,
                "raw_win_prob": getattr(self, 'last_raw_prob', win_prob),
                "smoothed_win_prob": getattr(self, 'last_smoothed_prob', win_prob),
                "calibrated_combined_prob": getattr(self, 'last_calibrated_combined', win_prob),
                "calibrated_win_prob": getattr(self, 'last_calibrated_prob', win_prob),
                "calibrated_phase_prob": getattr(self, 'last_calibrated_phase', win_prob),
                "calibrated_per_over_prob": getattr(self, 'last_calibrated_per_over', win_prob),
                "calibrated_phase_target_prob": getattr(self, 'last_calibrated_phase_target', win_prob),
                "inn2_router_phase": getattr(self.predictor, 'last_inn2_router_phase', None) if self.predictor else None,
                "inn2_router_source": getattr(self.predictor, 'last_inn2_router_source', None) if self.predictor else None,
                "inn2_router_raw_prob": getattr(self.predictor, 'last_inn2_router_raw_prob', None) if self.predictor else None,
                "inn2_router_output_prob": getattr(self.predictor, 'last_inn2_router_output_prob', None) if self.predictor else None,
                "post_model_calibration_rule": getattr(self.predictor, 'last_post_model_calibration_rule', None) if self.predictor else None,
                "post_model_calibration_input_prob": getattr(self.predictor, 'last_post_model_calibration_input', None) if self.predictor else None,
                "post_model_calibration_prob": getattr(self.predictor, 'last_post_model_calibration_prob', None) if self.predictor else None,
                "shadow_t_prob": getattr(self, 'last_shadow_prob', None),  # Shadow: segment-specific T
                "league": self.league,  # League code if --league was specified
                "inn1_stats_source": getattr(self, "_inn1_stats_source", "default"),
                "prediction_guard": getattr(self, "_prediction_guard", None),
                "league_calibrated_prob": (
                    getattr(self.predictor, 'last_league_calibrated', None)
                    if self.predictor else None
                ),
                "features": features,
                "odm": self.last_odm_prediction,
                "history": self._prediction_history[-50:],  # Last 50 data points
                # Market odds from CREX
                "market_fav_team": state.market_fav_team,
                "market_back_odds": state.market_back_odds,
                "market_lay_odds": state.market_lay_odds,
                "market_fav_prob": state.market_fav_prob,
                # Ensemble blending
                "ensemble_prob": getattr(self, '_last_ensemble_prob', None),
                "ensemble_source": getattr(self, '_last_ensemble_source', None),
                "ensemble_alpha": getattr(self, '_last_ensemble_alpha', None),
                # Candidate-only market-aware innings-2 overlay; never used as primary probability.
                "market_stack": getattr(self, '_last_market_stack', self.last_market_stack),
                "terminal_clamp": getattr(self, '_last_terminal_clamp', None),
                # Monte Carlo simulation results (uses league-calibrated win_prob for betting edge)
                "monte_carlo": self._run_monte_carlo_simulation(model_prob=win_prob, use_ml_model=self.use_ml_model),
                # Reduced-over / DLS / ODI fields
                "total_overs": self._effective_total_overs or self.format_config.total_overs,
                "revised_target": self._cli_revised_target,
                "format": self.format_config.format_name,
                "par_score": self.format_config.par_score,
                "mc_only": self.mc_only or (self._effective_total_overs or self.format_config.total_overs) < 20 or (self._effective_total_overs or self.format_config.total_overs) >= 40,
            }
            
            # Write atomically
            json_path = Path(self.output_json)
            tmp_path = json_path.with_suffix('.tmp')
            with open(tmp_path, 'w') as f:
                json.dump(output, f, indent=2)
            tmp_path.replace(json_path)

            if self.live_match_json:
                try:
                    from dataclasses import asdict

                    debug_payload = {
                        "timestamp": output["timestamp"],
                        "match_url": self.match_url,
                        "model_dir": self.model_dir,
                        "feature_store_dir": self.feature_store_dir,
                        "state": {
                            "batting_team": state.batting_team,
                            "bowling_team": state.bowling_team,
                            "score": state.total_runs,
                            "wickets": state.wickets,
                            "overs": state.overs,
                            "over": over,
                            "ball": ball,
                            "target": state.target,
                            "target_runs": state.target,  # alias for external consumers
                            "is_second_innings": state.is_second_innings,
                            "toss_decision": state.toss_decision,
                            "batsman1_name": state.batsman1_name,
                            "batsman1_runs": state.batsman1_runs,
                            "batsman1_balls": state.batsman1_balls,
                            "batsman2_name": state.batsman2_name,
                            "batsman2_runs": state.batsman2_runs,
                            "batsman2_balls": state.batsman2_balls,
                            "bowler1_name": state.bowler1_name,
                            "bowler1_overs": state.bowler1_overs,
                            "bowler1_runs": state.bowler1_runs,
                            "bowler1_wickets": state.bowler1_wickets,
                            "current_run_rate": state.current_run_rate,
                            "required_run_rate": state.required_run_rate,
                            "last_ball_number": self.last_ball_number,
                        },
                        "pred_state": asdict(pred_state) if pred_state else None,
                        "scraped_data": scraped_data,
                        "ball_history": ball_history,
                        "features": features,
                        "odm": self.last_odm_prediction,
                        "market_stack": output.get("market_stack"),
                        "terminal_clamp": output.get("terminal_clamp"),
                        "bat_win_prob": win_prob,
                        "bowl_win_prob": 1 - win_prob,
                        "history": self._prediction_history[-200:],
                        "balls_data": [asdict(b) for b in (state.balls_data or [])],
                    }

                    debug_path = Path(self.live_match_json)
                    debug_tmp = debug_path.with_suffix('.tmp')
                    with open(debug_tmp, 'w') as f:
                        json.dump(debug_payload, f, indent=2)
                    debug_tmp.replace(debug_path)
                except Exception:
                    pass
            
        except Exception as e:
            pass  # Don't interrupt the main flow
    
    async def stop(self):
        """Stop the predictor."""
        self._running = False
        if self.browser:
            try:
                await self.browser.close()
                print("\n[STOP] Browser closed")
            except Exception as e:
                print(f"\n[WARN] Browser close failed (ignored): {e}")
            finally:
                self.browser = None
        if self._playwright:
            try:
                await self._playwright.stop()
                print("[STOP] Playwright driver closed")
            except Exception as e:
                print(f"[WARN] Playwright driver close failed (ignored): {e}")
            finally:
                self._playwright = None


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Crex Live Match Predictor")
    parser.add_argument("--match-url", required=True, help="Crex match URL")
    parser.add_argument("--model-dir", default="models/champion_final", help="Model directory")
    parser.add_argument("--feature-store-dir", default=None, help="Feature store directory (for league-specific models)")
    parser.add_argument("--headless", action="store_true", default=True, help="Run headless")
    parser.add_argument("--poll-interval", type=float, default=2.0, help="Poll interval in seconds")
    parser.add_argument("--output-json", default=None, help="Output JSON file for Streamlit integration")
    parser.add_argument("--venue", default=None, help="Manually specify venue name")
    parser.add_argument(
        "--live-match-json",
        default=None,
        help="Optional richer per-match debug JSON (defaults to sibling livematch.json when --output-json is set)",
    )
    parser.add_argument(
        "--league",
        default=None,
        help="League code for league-specific calibration (e.g., 'ssm', 'bbl', 'sa20')",
    )
    parser.add_argument(
        "--odm-model-dir",
        default=None,
        help="Optional ODM advisory model directory for direction and interval output.",
    )
    parser.add_argument(
        "--use-ml-model",
        action="store_true",
        default=False,
        help="Use ML model for Monte Carlo terminal state evaluation (more accurate, ~50ms for 2000 sims)",
    )
    parser.add_argument(
        "--record-states",
        action="store_true",
        default=False,
        help="Enable match state recording to Parquet files for analysis",
    )
    parser.add_argument(
        "--states-dir",
        default=None,
        help="Directory for recorded match states (default: data/match_states/<league>/)",
    )
    parser.add_argument(
        "--total-overs",
        type=int,
        default=None,
        help="Total overs per innings (1-50). Auto-detected from CREX if not specified. "
             "When < 20, switches to MC-only prediction. When >= 40, uses ODI format.",
    )
    parser.add_argument(
        "--revised-target",
        type=int,
        default=None,
        help="DLS revised target for 2nd innings. Auto-detected from CREX if not specified.",
    )
    parser.add_argument(
        "--mc-only",
        action="store_true",
        default=False,
        help="Force Monte Carlo-only prediction mode. "
             "Bypasses the trained XGBLogRegEnsemble model. "
             "Automatically enabled for ODI (>= 40 overs) and reduced-over (< 20) matches.",
    )
    parser.add_argument(
        "--market-stack-model-dir",
        default=None,
        help="Optional IPL innings-2 market-stack candidate directory for dry-run overlay output.",
    )
    parser.add_argument(
        "--candidate-model-dir",
        default=None,
        help="Optional candidate model directory for seven-day shadow scoring; never used for live output.",
    )
    parser.add_argument(
        "--team1-name",
        default=None,
        help="Provider-authoritative first team name for this match.",
    )
    parser.add_argument(
        "--team2-name",
        default=None,
        help="Provider-authoritative second team name for this match.",
    )
    
    args = parser.parse_args()
    
    predictor = CrexLivePredictor(
        match_url=args.match_url,
        model_dir=args.model_dir,
        headless=args.headless,
        feature_store_dir=args.feature_store_dir,
        output_json=args.output_json,
        live_match_json=args.live_match_json,
        venue=args.venue,
        league=args.league,
        odm_model_dir=args.odm_model_dir,
        use_ml_model=args.use_ml_model,
        record_states=args.record_states,
        states_dir=args.states_dir,
        total_overs=args.total_overs,
        revised_target=args.revised_target,
        mc_only=args.mc_only,
        market_stack_model_dir=args.market_stack_model_dir,
        team1_name=args.team1_name,
        team2_name=args.team2_name,
        candidate_model_dir=args.candidate_model_dir,
    )
    
    await predictor.run(poll_interval=args.poll_interval)


if __name__ == "__main__":
    asyncio.run(main())
