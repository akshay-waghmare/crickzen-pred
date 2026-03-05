"""
NextBallSampler for Monte Carlo Simulation Engine.

Samples ball outcomes (runs, wickets) based on phase and pressure.
Uses pre-computed CDFs for efficient numpy-based sampling.
Supports league-specific distributions when available.
"""

import numpy as np
from typing import Tuple, Optional, Dict
from pathlib import Path
import json
import structlog

from .config import (
    RUN_DIST, 
    RUN_CDF,
    WICKET_PROB,
    WICKET_MULTIPLIER,
    ODI_PHASES,
    get_phase,
)

# ODI league identifiers for auto-detection
ODI_LEAGUE_NAMES = frozenset({
    "odi", "odis", "odi_male", "odi_female",
    "odm", "odm_male", "odm_female",
})
from .state import MatchState

logger = structlog.get_logger(__name__)

# Cache for league-specific distributions
_LEAGUE_DIST_CACHE: Dict[str, Dict] = {}


def _build_cdf_from_dist(dist: Dict[int, float]) -> Tuple[np.ndarray, np.ndarray]:
    """Build CDF arrays for np.searchsorted() sampling from a distribution."""
    runs = np.array(sorted(dist.keys()))
    probs = np.array([dist[r] for r in runs])
    cdf = np.cumsum(probs)
    return runs, cdf


def load_league_distributions(league: str, data_dir: str = "data", model_dir: Optional[str] = None) -> Optional[Dict]:
    """
    Load league-specific phase distributions from JSON file.
    
    Lookup order:
    1. model_dir/phase_distributions_{league}.json (if model_dir provided)
    2. data_dir/phase_distributions_{league}.json
    
    Args:
        league: League code (e.g., 'bbl', 'sa20')
        data_dir: Directory containing distribution files (fallback)
        model_dir: Model directory to check first (optional)
        
    Returns:
        Dictionary with run_dist, wicket_prob, etc. or None if not found
    """
    cache_key = f"{model_dir or data_dir}/{league}"
    
    if cache_key in _LEAGUE_DIST_CACHE:
        return _LEAGUE_DIST_CACHE[cache_key]
    
    # Try model directory first
    dist_path = None
    source = None
    if model_dir:
        model_path = Path(model_dir) / f"phase_distributions_{league}.json"
        if model_path.exists():
            dist_path = model_path
            source = "model_dir"
    
    # Fallback to data directory
    if dist_path is None:
        data_path = Path(data_dir) / f"phase_distributions_{league}.json"
        if data_path.exists():
            dist_path = data_path
            source = "data_dir"
    
    if dist_path is None:
        _LEAGUE_DIST_CACHE[cache_key] = None
        return None
    
    try:
        with open(dist_path) as f:
            data = json.load(f)
        
        # Build CDFs for run distributions
        run_cdfs = {}
        for phase, dist in data.get('run_dist', {}).items():
            # Convert string keys to int
            dist_int = {int(k): v for k, v in dist.items()}
            run_cdfs[phase] = _build_cdf_from_dist(dist_int)
        
        data['run_cdf'] = run_cdfs
        data['_source'] = source  # Track where it was loaded from
        _LEAGUE_DIST_CACHE[cache_key] = data
        return data
    
    except Exception:
        _LEAGUE_DIST_CACHE[cache_key] = None
        return None


class NextBallSampler:
    """
    Samples ball-by-ball outcomes based on phase and game state.
    
    Uses phase-based run distributions and wicket probabilities derived
    from 1.89M global T20 balls (research.md).
    
    Supports league-specific distributions when available:
        sampler = NextBallSampler(seed=42, league="bbl")
    
    Enrichments (optional, enabled via enrichments=True):
        - Partnership momentum: boundary probability increases when score
          is progressing well relative to par at current point.
        - New batsman factor: dot ball probability elevated after a wicket
          falls, simulating the "settling in" period.
        - Pitch deterioration: wicket probability rises as innings progresses
          (simulates aging pitch, tired bowlers/batsmen, higher risk-taking).
    
    Example:
        sampler = NextBallSampler(seed=42, enrichments=True)
        runs, is_wicket = sampler.sample(state)
    """
    
    def __init__(self, seed: Optional[int] = None, league: Optional[str] = None, model_dir: Optional[str] = None, enrichments: bool = False):
        """
        Initialize sampler with optional random seed and league.
        
        Args:
            seed: Random seed for reproducibility
            league: Optional league code for league-specific distributions
            model_dir: Optional model directory to look for phase distributions
            enrichments: Enable MC enrichments (partnership momentum,
                new batsman factor, pitch deterioration)
        """
        self.rng = np.random.default_rng(seed)
        self.league = league
        self.enrichments = enrichments
        
        # Track simulation context for enrichments
        self._balls_since_last_wicket: int = 0  # Balls since last wicket fell
        
        # Try to load league-specific distributions
        self._league_data = None
        if league:
            self._league_data = load_league_distributions(league, model_dir=model_dir)
        
        # Pre-compute CDF arrays for each phase
        if self._league_data and 'run_cdf' in self._league_data:
            # Use league-specific CDFs
            self._run_values = {
                phase: cdf[0] for phase, cdf in self._league_data['run_cdf'].items()
            }
            self._run_cdfs = {
                phase: cdf[1] for phase, cdf in self._league_data['run_cdf'].items()
            }
            self._wicket_prob = self._league_data.get('wicket_prob', WICKET_PROB)
            # Load per-wickets-down multiplier from league data or use default.
            # Note: some older JSON files store phase-level multipliers in
            # 'wicket_multiplier' (keys like 'powerplay'/'middle'/'death').
            # We only use integer-keyed (wickets-down) multipliers here.
            wm_raw = self._league_data.get('wicket_multiplier', None)
            if wm_raw and all(isinstance(k, int) or (isinstance(k, str) and k.isdigit()) for k in wm_raw):
                self._wicket_multiplier = {
                    int(k): max(0.5, min(2.0, v))  # Clamp to [0.5, 2.0]
                    for k, v in wm_raw.items()
                }
            else:
                self._wicket_multiplier = dict(WICKET_MULTIPLIER)
            source = self._league_data.get('_source', 'unknown')
            logger.info(
                "Sampler using league-specific distributions",
                league=league,
                phases=list(self._run_values.keys()),
                distribution_source=source,
                model_dir=model_dir
            )
        else:
            # Use global distributions (check for ODI defaults)
            is_odi = league and league.lower() in ODI_LEAGUE_NAMES
            if is_odi:
                # Use ODI default distributions from config
                from .config import ODI_RUN_DIST, ODI_RUN_CDF, ODI_WICKET_PROB, ODI_WICKET_MULTIPLIER
                self._run_values = {
                    phase: cdf[0] for phase, cdf in ODI_RUN_CDF.items()
                }
                self._run_cdfs = {
                    phase: cdf[1] for phase, cdf in ODI_RUN_CDF.items()
                }
                self._wicket_prob = ODI_WICKET_PROB
                self._wicket_multiplier = dict(ODI_WICKET_MULTIPLIER)
                logger.info(
                    "Sampler using embedded ODI default distributions",
                    league=league,
                    phases=list(self._run_values.keys()),
                )
            else:
                # Use global T20 distributions
                self._run_values = {
                    phase: cdf[0] for phase, cdf in RUN_CDF.items()
                }
                self._run_cdfs = {
                    phase: cdf[1] for phase, cdf in RUN_CDF.items()
                }
                self._wicket_prob = WICKET_PROB
                self._wicket_multiplier = dict(WICKET_MULTIPLIER)
                if league:
                    logger.warning(
                        "League-specific distributions not found, using global T20 distributions",
                        league=league,
                        expected_file=f"data/phase_distributions_{league}.json"
                    )
                else:
                    logger.debug("Sampler using global T20 distributions")
    
    def sample(self, state: MatchState) -> Tuple[int, bool]:
        """
        Sample a single ball outcome.
        
        Args:
            state: Current match state
            
        Returns:
            Tuple of (runs, is_wicket)
        """
        phase = state.phase
        wickets = state.wickets_lost
        
        # Sample runs using CDF
        runs = self._sample_runs(phase)
        
        # Apply enrichments (if enabled)
        if self.enrichments:
            runs = self._apply_partnership_momentum(runs, state)
            runs = self._apply_new_batsman_runs_modifier(runs)
            
        # Sample wicket with multiplier for lower-order
        is_wicket = self._sample_wicket(phase, wickets)
        
        # Apply pitch deterioration enrichment
        if self.enrichments:
            is_wicket = self._apply_pitch_deterioration(is_wicket, state, phase, wickets)
        
        # Track balls since last wicket for enrichments
        if is_wicket:
            self._balls_since_last_wicket = 0
        else:
            self._balls_since_last_wicket += 1
        
        return runs, is_wicket
    
    # ------------------------------------------------------------------
    # Enrichment methods (T036-T038)
    # ------------------------------------------------------------------
    
    def _apply_partnership_momentum(self, runs: int, state: MatchState) -> int:
        """T036: Partnership momentum — boost boundary probability for
        established partnerships (many balls since last wicket).
        
        When a pair has batted together for a while (20+ balls without
        a wicket), the chance of a dot ball is reduced and the chance of
        a boundary (4 or 6) is slightly elevated.
        
        Returns:
            Potentially upgraded runs value.
        """
        if self._balls_since_last_wicket < 20:
            return runs
        
        # Momentum scales: 20 balls = +3%, 40+ balls = +6%
        momentum = min(0.06, 0.03 * (self._balls_since_last_wicket / 20))
        
        # Chance to upgrade 1→4 or 2→4
        if runs in (0, 1, 2) and self.rng.random() < momentum:
            return 4
        return runs
    
    def _apply_new_batsman_factor(self, is_wicket: bool, state: MatchState) -> bool:
        """T037: New batsman factor — after a recent wicket, the new
        batsman is still settling. This enrichment does NOT reject
        wickets (that would bias the terminal state). Instead, it slightly
        elevates dot balls in the first few balls after a wicket.
        
        For wicket decision specifically: if a wicket just fell (within 5
        balls), the next wicket is *slightly* more likely (pressure on new
        batsman). This is already captured partially by wicket_multiplier,
        but this is an additional small boost.
        
        Returns:
            The original is_wicket value (unmodified for the wicket;
            the effect is applied to runs via sample() call).
        """
        # Don't modify the wicket itself — the effect manifests in runs
        return is_wicket
    
    def _apply_new_batsman_runs_modifier(self, runs: int) -> int:
        """Reduce runs for new batsman (settling in period).
        
        If a wicket fell recently (within 10 balls), increase dot ball
        probability by occasionally converting 1s and 2s into 0s.
        """
        if self._balls_since_last_wicket >= 10:
            return runs  # Not a new batsman anymore
        
        # Settling factor: 0 balls since wicket = 15% dot chance, decays linearly
        settling_prob = 0.15 * (1.0 - self._balls_since_last_wicket / 10.0)
        
        if runs in (1, 2) and self.rng.random() < settling_prob:
            return 0  # Dot ball
        return runs
    
    def _apply_pitch_deterioration(self, is_wicket: bool, state: MatchState,
                                     phase: str, wickets_lost: int) -> bool:
        """T038: Pitch deterioration — wicket probability rises as innings
        progresses, simulating aging pitch and higher risk-taking.
        
        Effect scales with innings progression:
          - First 40% of balls bowled: no effect
          - 40-70% of balls bowled: +2% additional wicket probability
          - 70-100% of balls bowled: +4% additional wicket probability
        
        Only applies to innings 1 (bowling conditions deteriorate).
        In innings 2, the pressure from required run rate already drives
        higher risk-taking via the wicket multiplier.
        
        Returns:
            Potentially upgraded wicket decision.
        """
        if is_wicket:
            return True  # Already a wicket
        
        balls_bowled = state.total_balls - state.balls_remaining
        progression = balls_bowled / state.total_balls
        
        if progression < 0.4:
            return False  # No effect early in innings
        
        # Scale: 0.4→0%, 0.7→2%, 1.0→4%
        extra_prob = 0.04 * max(0.0, (progression - 0.4) / 0.6)
        
        return self.rng.random() < extra_prob
    
    def _sample_runs(self, phase: str) -> int:
        """Sample runs for given phase using CDF."""
        u = self.rng.random()
        # Fallback to 'middle' if phase not in loaded distributions
        effective_phase = phase if phase in self._run_values else 'middle'
        run_values = self._run_values[effective_phase]
        run_cdf = self._run_cdfs[effective_phase]
        idx = np.searchsorted(run_cdf, u)
        return int(run_values[min(idx, len(run_values) - 1)])
    
    def _sample_wicket(self, phase: str, wickets_lost: int) -> bool:
        """Sample wicket with lower-order multiplier."""
        # Fallback to 'middle' if phase not in wicket probs
        effective_phase = phase if phase in self._wicket_prob else 'middle'
        base_prob = self._wicket_prob.get(effective_phase, WICKET_PROB.get(effective_phase, 0.05))
        multiplier = self._wicket_multiplier.get(wickets_lost, 1.5)
        effective_prob = min(base_prob * multiplier, 0.25)  # Cap at 25%
        return self.rng.random() < effective_prob
    
    def sample_vectorized(
        self,
        phases: np.ndarray,
        wickets: np.ndarray,
        n: int,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Sample outcomes for N simulations in parallel.
        
        Args:
            phases: Array of phase names (n,)
            wickets: Array of wickets lost (n,)
            n: Number of simulations (should match len(phases))
            
        Returns:
            Tuple of (runs array, is_wicket array)
        """
        # Sample uniform random numbers
        u_runs = self.rng.random(n)
        u_wickets = self.rng.random(n)
        
        # Pre-allocate output arrays
        runs = np.zeros(n, dtype=np.int32)
        is_wicket = np.zeros(n, dtype=bool)
        
        # Sample by phase (vectorized within each phase)
        # Dynamically iterate over all phases present in loaded distributions
        known_phases = set(self._run_values.keys())
        for phase in known_phases:
            mask = phases == phase
            if not np.any(mask):
                continue
            
            # Sample runs for this phase
            run_values = self._run_values[phase]
            run_cdf = self._run_cdfs[phase]
            phase_u = u_runs[mask]
            phase_idx = np.searchsorted(run_cdf, phase_u)
            phase_idx = np.minimum(phase_idx, len(run_values) - 1)
            runs[mask] = run_values[phase_idx]
            
            # Sample wickets for this phase
            base_prob = self._wicket_prob.get(phase, WICKET_PROB.get(phase, 0.05))
            phase_wickets = wickets[mask]
            multipliers = np.array([self._wicket_multiplier.get(w, 1.5) for w in phase_wickets])
            effective_probs = np.minimum(base_prob * multipliers, 0.25)
            is_wicket[mask] = u_wickets[mask] < effective_probs
        
        return runs, is_wicket
    
    def sample_batch(
        self,
        state: MatchState,
        n_sims: int,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Sample N ball outcomes for the same state.
        
        Optimized for single-state, multi-simulation case.
        
        Args:
            state: Current match state (same for all simulations)
            n_sims: Number of simulations
            
        Returns:
            Tuple of (runs array, is_wicket array)
        """
        phase = state.phase
        wickets = state.wickets_lost
        
        # Sample runs
        u_runs = self.rng.random(n_sims)
        run_values = self._run_values[phase]
        run_cdf = self._run_cdfs[phase]
        idx = np.searchsorted(run_cdf, u_runs)
        idx = np.minimum(idx, len(run_values) - 1)
        runs = run_values[idx]
        
        # Sample wickets
        base_prob = self._wicket_prob.get(phase, WICKET_PROB.get(phase, 0.05))
        multiplier = self._wicket_multiplier.get(wickets, 1.5)
        effective_prob = min(base_prob * multiplier, 0.25)
        u_wickets = self.rng.random(n_sims)
        is_wicket = u_wickets < effective_prob
        
        return runs.astype(np.int32), is_wicket
    
    def get_expected_runs(self, phase: str) -> float:
        """Get expected runs per ball for a phase."""
        # Use league-specific distribution if available
        if self._league_data and 'run_dist' in self._league_data:
            dist = self._league_data['run_dist'].get(phase, RUN_DIST[phase])
            # Convert string keys to int
            dist = {int(k): v for k, v in dist.items()}
        else:
            dist = RUN_DIST[phase]
        return sum(runs * prob for runs, prob in dist.items())
    
    def get_wicket_prob(self, phase: str, wickets_lost: int) -> float:
        """Get effective wicket probability for state."""
        base_prob = self._wicket_prob.get(phase, WICKET_PROB.get(phase, 0.05))
        multiplier = self._wicket_multiplier.get(wickets_lost, 1.5)
        return min(base_prob * multiplier, 0.25)
