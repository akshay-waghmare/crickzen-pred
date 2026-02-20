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
    get_phase,
)
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
    
    Example:
        sampler = NextBallSampler(seed=42)
        runs, is_wicket = sampler.sample(state)
    """
    
    def __init__(self, seed: Optional[int] = None, league: Optional[str] = None, model_dir: Optional[str] = None):
        """
        Initialize sampler with optional random seed and league.
        
        Args:
            seed: Random seed for reproducibility
            league: Optional league code for league-specific distributions
            model_dir: Optional model directory to look for phase distributions
        """
        self.rng = np.random.default_rng(seed)
        self.league = league
        
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
            source = self._league_data.get('_source', 'unknown')
            logger.info(
                "Sampler using league-specific distributions",
                league=league,
                phases=list(self._run_values.keys()),
                distribution_source=source,
                model_dir=model_dir
            )
        else:
            # Use global distributions
            self._run_values = {
                phase: cdf[0] for phase, cdf in RUN_CDF.items()
            }
            self._run_cdfs = {
                phase: cdf[1] for phase, cdf in RUN_CDF.items()
            }
            self._wicket_prob = WICKET_PROB
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
        
        # Sample wicket with multiplier for lower-order
        is_wicket = self._sample_wicket(phase, wickets)
        
        return runs, is_wicket
    
    def _sample_runs(self, phase: str) -> int:
        """Sample runs for given phase using CDF."""
        u = self.rng.random()
        run_values = self._run_values[phase]
        run_cdf = self._run_cdfs[phase]
        idx = np.searchsorted(run_cdf, u)
        return int(run_values[min(idx, len(run_values) - 1)])
    
    def _sample_wicket(self, phase: str, wickets_lost: int) -> bool:
        """Sample wicket with lower-order multiplier."""
        base_prob = self._wicket_prob.get(phase, WICKET_PROB[phase])
        multiplier = WICKET_MULTIPLIER.get(wickets_lost, 1.5)
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
        for phase in ("powerplay", "middle", "death"):
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
            base_prob = self._wicket_prob.get(phase, WICKET_PROB[phase])
            phase_wickets = wickets[mask]
            multipliers = np.array([WICKET_MULTIPLIER.get(w, 1.5) for w in phase_wickets])
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
        base_prob = self._wicket_prob.get(phase, WICKET_PROB[phase])
        multiplier = WICKET_MULTIPLIER.get(wickets, 1.5)
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
        base_prob = self._wicket_prob.get(phase, WICKET_PROB[phase])
        multiplier = WICKET_MULTIPLIER.get(wickets_lost, 1.5)
        return min(base_prob * multiplier, 0.25)
