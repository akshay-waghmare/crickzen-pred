"""
NextBallSampler for Monte Carlo Simulation Engine.

Samples ball outcomes (runs, wickets) based on phase and pressure.
Uses pre-computed CDFs for efficient numpy-based sampling.
"""

import numpy as np
from typing import Tuple, Optional

from .config import (
    RUN_DIST,
    RUN_CDF,
    WICKET_PROB,
    WICKET_MULTIPLIER,
    get_phase,
)
from .state import MatchState


class NextBallSampler:
    """
    Samples ball-by-ball outcomes based on phase and game state.
    
    Uses phase-based run distributions and wicket probabilities derived
    from 1.89M global T20 balls (research.md).
    
    Example:
        sampler = NextBallSampler(seed=42)
        runs, is_wicket = sampler.sample(state)
    """
    
    def __init__(self, seed: Optional[int] = None):
        """
        Initialize sampler with optional random seed.
        
        Args:
            seed: Random seed for reproducibility
        """
        self.rng = np.random.default_rng(seed)
        
        # Pre-compute CDF arrays for each phase
        self._run_values = {
            phase: cdf[0] for phase, cdf in RUN_CDF.items()
        }
        self._run_cdfs = {
            phase: cdf[1] for phase, cdf in RUN_CDF.items()
        }
    
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
        base_prob = WICKET_PROB[phase]
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
            base_prob = WICKET_PROB[phase]
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
        base_prob = WICKET_PROB[phase]
        multiplier = WICKET_MULTIPLIER.get(wickets, 1.5)
        effective_prob = min(base_prob * multiplier, 0.25)
        u_wickets = self.rng.random(n_sims)
        is_wicket = u_wickets < effective_prob
        
        return runs.astype(np.int32), is_wicket
    
    def get_expected_runs(self, phase: str) -> float:
        """Get expected runs per ball for a phase."""
        dist = RUN_DIST[phase]
        return sum(runs * prob for runs, prob in dist.items())
    
    def get_wicket_prob(self, phase: str, wickets_lost: int) -> float:
        """Get effective wicket probability for state."""
        base_prob = WICKET_PROB[phase]
        multiplier = WICKET_MULTIPLIER.get(wickets_lost, 1.5)
        return min(base_prob * multiplier, 0.25)
