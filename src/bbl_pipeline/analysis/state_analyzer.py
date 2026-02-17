"""
State Analyzer for Match State Data.

Consolidates recorded match states, computes calibration metrics (Brier, ECE, LogLoss),
analyzes deviation patterns, and generates reports.

Classes:
    StateAnalyzer: Main analysis engine for recorded match states
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional, Dict, Any, List
import structlog
from sklearn.metrics import log_loss, brier_score_loss


log = structlog.get_logger()


class StateAnalyzer:
    """
    Analyzer for recorded match state data.
    
    Loads match state Parquet files, consolidates across matches,
    computes calibration metrics, and generates reports.
    
    Attributes:
        league: League identifier (e.g., "bbl", "sa20")
        states_dir: Directory containing match Parquet files
        match_files: List of discovered match Parquet files
        metadata_file: Path to match_metadata.parquet
    """
    
    def __init__(
        self,
        league: str,
        states_dir: Path,
    ):
        """
        Initialize StateAnalyzer.
        
        Args:
            league: League identifier
            states_dir: Directory containing match state Parquet files
        """
        self.league = league
        self.states_dir = Path(states_dir)
        self.log = log.bind(league=league, states_dir=str(states_dir))
        
        # Discover available files
        self.match_files = sorted(self.states_dir.glob("*.parquet"))
        self.match_files = [f for f in self.match_files if f.name not in ["match_metadata.parquet", "all_matches.parquet", "volatility_profiles.parquet", "signal_events.parquet"]]
        
        self.metadata_file = self.states_dir / "match_metadata.parquet"
        self.consolidated_file = self.states_dir / "all_matches.parquet"
        
        self.log.info(
            "state_analyzer_initialized",
            num_matches=len(self.match_files),
            has_metadata=self.metadata_file.exists(),
        )
    
    def consolidate(self) -> pd.DataFrame:
        """
        Consolidate all match Parquet files into a single DataFrame.
        
        Reads all <match_id>.parquet files, concatenates them, sorts by
        match_id + innings + over_number + ball_in_over, and writes to
        all_matches.parquet.
        
        Returns:
            Consolidated DataFrame with all ball states
        """
        if len(self.match_files) == 0:
            self.log.warning("no_match_files_found")
            return pd.DataFrame()
        
        self.log.info("consolidating_matches", num_files=len(self.match_files))
        
        # Read all match files
        dfs = []
        for match_file in self.match_files:
            try:
                df = pd.read_parquet(match_file)
                dfs.append(df)
            except Exception as e:
                self.log.error("failed_to_read_match_file", file=str(match_file), error=str(e))
        
        if len(dfs) == 0:
            self.log.warning("no_valid_match_files")
            return pd.DataFrame()
        
        # Concatenate
        consolidated = pd.concat(dfs, ignore_index=True)
        
        # Sort by match_id, innings, over_number, ball_in_over
        consolidated = consolidated.sort_values(
            by=["match_id", "innings", "over_number", "ball_in_over"],
            ignore_index=True,
        )
        
        # Write to all_matches.parquet
        consolidated.to_parquet(self.consolidated_file, index=False)
        
        self.log.info(
            "consolidation_complete",
            total_balls=len(consolidated),
            output_file=str(self.consolidated_file),
        )
        
        return consolidated
    
    def calibration_report(
        self,
        output_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """
        Generate calibration drift report with Brier, ECE, LogLoss metrics.
        
        Loads all_matches.parquet + match_metadata.parquet, joins on match_id
        to get winner, computes actual_win (batting_team == winner), then
        calculates calibration metrics overall + by innings + by phase + by team_tier.
        
        Writes formatted markdown report to CALIBRATION_REPORT.md.
        
        Args:
            output_path: Optional custom output path for report (default: states_dir/CALIBRATION_REPORT.md)
            
        Returns:
            Dict with metrics by segment
        """
        # Load consolidated data
        if not self.consolidated_file.exists():
            self.log.warning("consolidated_file_not_found")
            self.consolidate()
        
        df = pd.read_parquet(self.consolidated_file)
        
        # Load metadata
        if not self.metadata_file.exists():
            self.log.warning("metadata_file_not_found")
            metadata = pd.DataFrame()
        else:
            metadata = pd.read_parquet(self.metadata_file)
        
        # Join to get winner
        if len(metadata) > 0:
            df = df.merge(metadata[["match_id", "winner"]], on="match_id", how="left")
        else:
            df["winner"] = None
        
        # Compute actual_win (batting team won)
        df["actual_win"] = (df["batting_team"] == df["winner"]).astype(int)
        
        # Filter out rows with no outcome (incomplete matches)
        df = df[df["winner"].notna()].copy()
        
        if len(df) == 0:
            self.log.warning("no_completed_matches_with_outcomes")
            return {}
        
        # Compute metrics
        results = {}
        
        # Overall
        results["overall"] = self._compute_metrics(df, "Overall")
        
        # By innings
        for innings in df["innings"].unique():
            innings_df = df[df["innings"] == innings]
            results[f"innings_{innings}"] = self._compute_metrics(innings_df, f"Innings {innings}")
        
        # By phase
        for phase in ["powerplay", "middle", "death"]:
            phase_df = df[df["match_phase"] == phase]
            if len(phase_df) > 0:
                results[f"phase_{phase}"] = self._compute_metrics(phase_df, phase.capitalize())
        
        # By team tier (if available)
        for tier in ["top", "mid", "bottom"]:
            tier_df = df[df["batting_team_tier"] == tier]
            if len(tier_df) > 0:
                results[f"tier_{tier}"] = self._compute_metrics(tier_df, f"Team Tier: {tier.capitalize()}")
        
        # Write markdown report
        if output_path is None:
            output_path = self.states_dir / "CALIBRATION_REPORT.md"
        
        self._write_calibration_report(results, output_path, len(df))
        
        self.log.info("calibration_report_generated", output_path=str(output_path))
        
        return results
    
    def _compute_metrics(self, df: pd.DataFrame, segment_name: str) -> Dict[str, Any]:
        """
        Compute Brier, ECE, and LogLoss for a data segment.
        
        Args:
            df: DataFrame with model_prob_final and actual_win columns
            segment_name: Name of segment for logging
            
        Returns:
            Dict with metrics: brier, ece, log_loss, sample_count
        """
        if len(df) == 0:
            return {"brier": None, "ece": None, "log_loss": None, "sample_count": 0}
        
        y_true = df["actual_win"].values
        y_pred = df["model_prob_final"].values
        
        # Brier score
        brier = brier_score_loss(y_true, y_pred)
        
        # ECE (10-bin)
        ece = self._compute_ece(y_true, y_pred, n_bins=10)
        
        # Log loss
        ll = log_loss(y_true, y_pred, labels=[0, 1])
        
        return {
            "segment": segment_name,
            "brier": float(brier),
            "ece": float(ece),
            "log_loss": float(ll),
            "sample_count": len(df),
        }
    
    def _compute_ece(self, y_true: np.ndarray, y_pred: np.ndarray, n_bins: int = 10) -> float:
        """
        Compute Expected Calibration Error (ECE) with histogram binning.
        
        Args:
            y_true: True binary labels (0 or 1)
            y_pred: Predicted probabilities (0.0 to 1.0)
            n_bins: Number of bins for calibration curve
            
        Returns:
            ECE value (0.0 = perfect calibration)
        """
        bin_edges = np.linspace(0, 1, n_bins + 1)
        bin_indices = np.digitize(y_pred, bin_edges[:-1]) - 1
        bin_indices = np.clip(bin_indices, 0, n_bins - 1)
        
        ece = 0.0
        total_samples = len(y_true)
        
        for i in range(n_bins):
            mask = bin_indices == i
            if mask.sum() == 0:
                continue
            
            bin_acc = y_true[mask].mean()
            bin_conf = y_pred[mask].mean()
            bin_count = mask.sum()
            
            ece += (bin_count / total_samples) * abs(bin_acc - bin_conf)
        
        return ece
    
    def _write_calibration_report(
        self,
        results: Dict[str, Any],
        output_path: Path,
        total_balls: int,
    ) -> None:
        """
        Write calibration metrics to markdown report.
        
        Args:
            results: Dict of metrics by segment
            output_path: Output file path
            total_balls: Total number of ball states analyzed
        """
        with open(output_path, "w") as f:
            f.write(f"# Calibration Report: {self.league.upper()}\n\n")
            f.write(f"**Generated**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"**Total Ball States**: {total_balls:,}\n")
            f.write(f"**League**: {self.league}\n\n")
            
            # Overall metrics
            if "overall" in results:
                overall = results["overall"]
                f.write("## Overall Calibration\n\n")
                f.write(f"- **Brier Score**: {overall['brier']:.4f}\n")
                f.write(f"- **ECE (10-bin)**: {overall['ece']:.4f}\n")
                f.write(f"- **Log Loss**: {overall['log_loss']:.4f}\n")
                f.write(f"- **Sample Count**: {overall['sample_count']:,}\n\n")
            
            # By innings
            f.write("## Calibration by Innings\n\n")
            f.write("| Innings | Brier | ECE | LogLoss | Samples |\n")
            f.write("|---------|-------|-----|---------|----------|\n")
            for key in sorted([k for k in results.keys() if k.startswith("innings_")]):
                metrics = results[key]
                f.write(f"| {metrics['segment']} | {metrics['brier']:.4f} | {metrics['ece']:.4f} | {metrics['log_loss']:.4f} | {metrics['sample_count']:,} |\n")
            f.write("\n")
            
            # By phase
            f.write("## Calibration by Match Phase\n\n")
            f.write("| Phase | Brier | ECE | LogLoss | Samples |\n")
            f.write("|-------|-------|-----|---------|----------|\n")
            for phase in ["powerplay", "middle", "death"]:
                key = f"phase_{phase}"
                if key in results:
                    metrics = results[key]
                    f.write(f"| {metrics['segment']} | {metrics['brier']:.4f} | {metrics['ece']:.4f} | {metrics['log_loss']:.4f} | {metrics['sample_count']:,} |\n")
            f.write("\n")
            
            # By team tier
            f.write("## Calibration by Team Tier\n\n")
            f.write("| Tier | Brier | ECE | LogLoss | Samples |\n")
            f.write("|------|-------|-----|---------|----------|\n")
            for tier in ["top", "mid", "bottom"]:
                key = f"tier_{tier}"
                if key in results:
                    metrics = results[key]
                    f.write(f"| {metrics['segment']} | {metrics['brier']:.4f} | {metrics['ece']:.4f} | {metrics['log_loss']:.4f} | {metrics['sample_count']:,} |\n")
            f.write("\n")
            
            f.write("---\n\n")
            f.write("**Interpretation:**\n")
            f.write("- **Brier Score**: Lower is better (0 = perfect predictions, 1 = worst)\n")
            f.write("- **ECE (Expected Calibration Error)**: Lower is better (0 = perfect calibration)\n")
            f.write("- **Log Loss**: Lower is better (penalizes confident wrong predictions)\n")
    
    def extract_signals(
        self,
        deviation_threshold: float = 0.10,
        reversion_threshold: float = 0.50,
    ) -> pd.DataFrame:
        """
        Extract signal events with price reversion labels for meta-model training.
        
        For each ball where |deviation| > threshold, scans forward to detect if
        market probability moves >= reversion_threshold (50%) back toward model
        within the same match.
        
        Computes:
        - price_reverted: bool (did market move >= 50% toward model?)
        - reversion_magnitude: float (0.0-1.0, how much of gap closed)
        - balls_to_reversion: int (how many balls until reversion, or None)
        
        Args:
            deviation_threshold: Minimum |deviation| to qualify as signal (default: 0.10)
            reversion_threshold: Fraction of deviation gap that must close (default: 0.50)
            
        Returns:
            DataFrame of signal events with reversion labels
        """
        # Load consolidated data
        if not self.consolidated_file.exists():
            self.log.warning("consolidated_file_not_found")
            self.consolidate()
        
        df = pd.read_parquet(self.consolidated_file)
        
        # Filter to balls with significant deviation
        signal_balls = df[df["deviation_abs"] >= deviation_threshold].copy()
        
        if len(signal_balls) == 0:
            self.log.warning("no_signal_events_found", threshold=deviation_threshold)
            return pd.DataFrame()
        
        self.log.info("extracting_signals", signal_count=len(signal_balls), threshold=deviation_threshold)
        
        # For each signal, scan forward for price reversion
        signal_events = []
        
        for idx, signal_row in signal_balls.iterrows():
            match_id = signal_row["match_id"]
            signal_innings = signal_row["innings"]
            signal_over = signal_row["over_number"]
            signal_ball = signal_row["ball_in_over"]
            
            deviation = signal_row["deviation"]
            model_prob = signal_row["model_prob_final"]
            market_prob_initial = signal_row["market_batting_team_prob"]
            
            # Get subsequent balls in same match
            future_balls = df[
                (df["match_id"] == match_id) &
                (df["innings"] == signal_innings) &
                (
                    (df["over_number"] > signal_over) |
                    ((df["over_number"] == signal_over) & (df["ball_in_over"] > signal_ball))
                )
            ].sort_values(["over_number", "ball_in_over"])
            
            # Detect reversion
            price_reverted = False
            reversion_magnitude = 0.0
            balls_to_reversion = None
            
            for future_idx, future_row in future_balls.iterrows():
                if pd.isna(future_row["market_batting_team_prob"]):
                    continue
                
                market_prob_current = future_row["market_batting_team_prob"]
                
                # Compute how much gap closed
                initial_gap = abs(model_prob - market_prob_initial)
                remaining_gap = abs(model_prob - market_prob_current)
                
                if initial_gap > 0:
                    magnitude = (initial_gap - remaining_gap) / initial_gap
                else:
                    magnitude = 0.0
                
                # Check if reversion threshold met
                if magnitude >= reversion_threshold:
                    price_reverted = True
                    reversion_magnitude = magnitude
                    
                    # Compute balls_to_reversion
                    balls_to_reversion = (
                        (future_row["over_number"] - signal_over) * 6 +
                        (future_row["ball_in_over"] - signal_ball)
                    )
                    break
            
            # Create signal event record
            signal_event = {
                "match_id": match_id,
                "league": signal_row["league"],
                "venue": signal_row["venue"],
                "innings": signal_innings,
                "over_number": signal_over,
                "ball_in_over": signal_ball,
                "batting_team": signal_row["batting_team"],
                "bowling_team": signal_row["bowling_team"],
                "batting_team_tier": signal_row["batting_team_tier"],
                "bowling_team_tier": signal_row["bowling_team_tier"],
                "match_phase": signal_row["match_phase"],
                "deviation": deviation,
                "deviation_abs": signal_row["deviation_abs"],
                "deviation_bucket": signal_row["deviation_bucket"],
                "deviation_direction": signal_row["deviation_direction"],
                "model_prob_final": model_prob,
                "market_batting_team_prob": market_prob_initial,
                "price_reverted": price_reverted,
                "reversion_magnitude": reversion_magnitude,
                "balls_to_reversion": balls_to_reversion,
                "timestamp": signal_row["timestamp"],
            }
            
            signal_events.append(signal_event)
        
        # Convert to DataFrame
        signal_df = pd.DataFrame(signal_events)
        
        # Write to signal_events.parquet
        output_file = self.states_dir / "signal_events.parquet"
        signal_df.to_parquet(output_file, index=False)
        
        self.log.info(
            "signal_extraction_complete",
            total_signals=len(signal_df),
            reverted_count=signal_df["price_reverted"].sum(),
            reversion_rate=signal_df["price_reverted"].mean(),
            output_file=str(output_file),
        )
        
        return signal_df
    
    def meta_model_readiness(self) -> Dict[str, Any]:
        """
        Check dataset readiness for meta-model training.
        
        Counts:
        - Total matches with metadata
        - Total signal events (with deviation > threshold)
        - Feature completeness percentage
        - Samples per deviation bucket
        
        Prints warning if < 200 matches (FR-029).
        
        Returns:
            Dict with readiness metrics
        """
        readiness = {}
        
        # Count matches
        if self.metadata_file.exists():
            metadata = pd.read_parquet(self.metadata_file)
            total_matches = len(metadata)
            completed_matches = len(metadata[metadata["result_type"] == "completed"])
        else:
            total_matches = 0
            completed_matches = 0
        
        readiness["total_matches"] = total_matches
        readiness["completed_matches"] = completed_matches
        
        # Count signal events
        signal_file = self.states_dir / "signal_events.parquet"
        if signal_file.exists():
            signals = pd.read_parquet(signal_file)
            total_signals = len(signals)
            reverted_signals = signals["price_reverted"].sum()
            
            # Samples per bucket
            bucket_counts = signals["deviation_bucket"].value_counts().to_dict()
        else:
            total_signals = 0
            reverted_signals = 0
            bucket_counts = {}
        
        readiness["total_signal_events"] = total_signals
        readiness["reverted_signal_events"] = int(reverted_signals)
        readiness["reversion_rate"] = reverted_signals / total_signals if total_signals > 0 else 0.0
        readiness["samples_per_bucket"] = bucket_counts
        
        # Feature completeness (check for non-null key features)
        if self.consolidated_file.exists():
            df = pd.read_parquet(self.consolidated_file)
            
            key_features = [
                "model_prob_final",
                "market_batting_team_prob",
                "deviation",
                "match_phase",
                "batting_team_tier",
            ]
            
            completeness = {}
            for feat in key_features:
                if feat in df.columns:
                    completeness[feat] = 1.0 - df[feat].isna().mean()
                else:
                    completeness[feat] = 0.0
            
            readiness["feature_completeness"] = completeness
        else:
            readiness["feature_completeness"] = {}
        
        # Check readiness threshold (FR-029)
        readiness["ready_for_meta_model"] = completed_matches >= 200 and total_signals >= 1000
        
        if not readiness["ready_for_meta_model"]:
            self.log.warning(
                "meta_model_not_ready",
                matches=completed_matches,
                signals=total_signals,
                required_matches=200,
                required_signals=1000,
            )
        
        return readiness
    
    def deviation_analysis(
        self,
        segment_by: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Analyze profitability segmented by deviation bucket.
        
        Loads signal_events.parquet, groups by deviation_bucket, computes:
        - Sample count
        - Success rate (model_team_won = batting team win when model was higher)
        - Average deviation
        - Expected value
        
        Supports segmentation by team_tier, match_phase, league.
        
        Args:
            segment_by: List of columns to segment by (e.g., ["match_phase", "batting_team_tier"])
            
        Returns:
            DataFrame with deviation analysis by bucket
        """
        signal_file = self.states_dir / "signal_events.parquet"
        
        if not signal_file.exists():
            self.log.warning("signal_events_not_found")
            return pd.DataFrame()
        
        signals = pd.read_parquet(signal_file)
        
        # Load metadata to get winners
        if self.metadata_file.exists():
            metadata = pd.read_parquet(self.metadata_file)
            signals = signals.merge(metadata[["match_id", "winner"]], on="match_id", how="left")
        else:
            self.log.warning("metadata_not_found_for_deviation_analysis")
            return pd.DataFrame()
        
        # Compute model_team_won (batting team won when deviation positive, bowling team won when negative)
        signals["model_team_won"] = (
            ((signals["deviation"] > 0) & (signals["batting_team"] == signals["winner"])) |
            ((signals["deviation"] < 0) & (signals["bowling_team"] == signals["winner"]))
        ).astype(int)
        
        # Group by bucket (and optional segments)
        group_cols = ["deviation_bucket"]
        if segment_by:
            group_cols.extend([col for col in segment_by if col in signals.columns])
        
        analysis = signals.groupby(group_cols).agg({
            "match_id": "count",
            "model_team_won": "mean",
            "deviation_abs": "mean",
            "price_reverted": "mean",
        }).reset_index()
        
        analysis.columns = ["_".join(col).strip("_") if isinstance(col, tuple) else col for col in analysis.columns]
        analysis.rename(columns={
            "match_id": "sample_count",
            "model_team_won": "success_rate",
            "deviation_abs": "avg_deviation",
            "price_reverted": "reversion_rate",
        }, inplace=True)
        
        # Compute expected value (simplified: success_rate - 0.5, assuming 50% market prob)
        analysis["expected_value"] = analysis["success_rate"] - 0.5
        
        # Sort by deviation bucket
        bucket_order = ["0.00-0.05", "0.05-0.10", "0.10-0.15", "0.15-0.20", "0.20-0.25", "0.25-0.30", "0.30+"]
        analysis["bucket_sort"] = analysis["deviation_bucket"].apply(lambda x: bucket_order.index(x) if x in bucket_order else 999)
        analysis = analysis.sort_values("bucket_sort").drop(columns=["bucket_sort"])
        
        self.log.info("deviation_analysis_complete", num_buckets=len(analysis))
        
        return analysis
    
    def compute_volatility(self) -> pd.DataFrame:
        """
        Compute volatility profiles for each match.
        
        Loads match Parquet files, computes std dev of model_prob_delta and
        market_prob_delta (overall + per innings), max swing, volatility ratio.
        
        Appends to volatility_profiles.parquet.
        
        Returns:
            DataFrame with volatility metrics per match
        """
        if len(self.match_files) == 0:
            self.log.warning("no_match_files_for_volatility")
            return pd.DataFrame()
        
        self.log.info("computing_volatility", num_matches=len(self.match_files))
        
        volatility_profiles = []
        
        for match_file in self.match_files:
            try:
                df = pd.read_parquet(match_file)
                match_id = match_file.stem
                
                # Overall volatility
                model_volatility = df["model_prob_delta"].std()
                market_volatility = df["market_prob_delta"].std()
                
                # Per innings volatility
                inn1_df = df[df["innings"] == 1]
                inn2_df = df[df["innings"] == 2]
                
                model_volatility_inn1 = inn1_df["model_prob_delta"].std() if len(inn1_df) > 0 else None
                market_volatility_inn1 = inn1_df["market_prob_delta"].std() if len(inn1_df) > 0 else None
                
                model_volatility_inn2 = inn2_df["model_prob_delta"].std() if len(inn2_df) > 0 else None
                market_volatility_inn2 = inn2_df["market_prob_delta"].std() if len(inn2_df) > 0 else None
                
                # Max swings
                model_max_swing = df["model_prob_delta"].abs().max()
                market_max_swing = df["market_prob_delta"].abs().max()
                
                # Volatility ratio
                volatility_ratio = model_volatility / market_volatility if market_volatility > 0 else None
                
                profile = {
                    "match_id": match_id,
                    "league": df["league"].iloc[0] if len(df) > 0 else None,
                    "model_volatility": model_volatility,
                    "market_volatility": market_volatility,
                    "volatility_ratio": volatility_ratio,
                    "model_volatility_inn1": model_volatility_inn1,
                    "market_volatility_inn1": market_volatility_inn1,
                    "model_volatility_inn2": model_volatility_inn2,
                    "market_volatility_inn2": market_volatility_inn2,
                    "model_max_swing": model_max_swing,
                    "market_max_swing": market_max_swing,
                }
                
                volatility_profiles.append(profile)
                
            except Exception as e:
                self.log.error("failed_to_compute_volatility", match_file=str(match_file), error=str(e))
        
        if len(volatility_profiles) == 0:
            self.log.warning("no_volatility_profiles_computed")
            return pd.DataFrame()
        
        volatility_df = pd.DataFrame(volatility_profiles)
        
        # Write to volatility_profiles.parquet
        output_file = self.states_dir / "volatility_profiles.parquet"
        volatility_df.to_parquet(output_file, index=False)
        
        self.log.info("volatility_computation_complete", num_profiles=len(volatility_df), output_file=str(output_file))
        
        return volatility_df
    
    def recovery_analysis(self) -> pd.DataFrame:
        """
        Analyze recovery patterns for strong teams under pressure.
        
        Filters signal events for top-tier batting team under stress:
        - 3+ wickets in powerplay, OR
        - 30+ runs behind required run rate in chase
        
        Computes recovery premium = actual_win_rate - model_prob.
        Segments by match phase.
        
        Returns:
            DataFrame with recovery premium by stress scenario
        """
        signal_file = self.states_dir / "signal_events.parquet"
        
        if not signal_file.exists():
            self.log.warning("signal_events_not_found")
            return pd.DataFrame()
        
        signals = pd.read_parquet(signal_file)
        
        # Load consolidated data for more context
        if self.consolidated_file.exists():
            df = pd.read_parquet(self.consolidated_file)
        else:
            df = pd.DataFrame()
        
        # Load metadata for winners
        if self.metadata_file.exists():
            metadata = pd.read_parquet(self.metadata_file)
            signals = signals.merge(metadata[["match_id", "winner"]], on="match_id", how="left")
        else:
            self.log.warning("metadata_not_found_for_recovery_analysis")
            return pd.DataFrame()
        
        # Filter for top-tier teams
        top_tier_signals = signals[signals["batting_team_tier"] == "top"].copy()
        
        # Define stress conditions (simplified — full implementation would join with consolidated data)
        # For now, use deviation as proxy for pressure
        stress_signals = top_tier_signals[top_tier_signals["deviation"] < -0.10].copy()
        
        if len(stress_signals) == 0:
            self.log.warning("no_stress_scenarios_found")
            return pd.DataFrame()
        
        # Compute actual win rate
        stress_signals["actual_win"] = (stress_signals["batting_team"] == stress_signals["winner"]).astype(int)
        
        # Group by match phase
        recovery = stress_signals.groupby("match_phase").agg({
            "match_id": "count",
            "actual_win": "mean",
            "model_prob_final": "mean",
        }).reset_index()
        
        recovery.rename(columns={
            "match_id": "sample_count",
            "actual_win": "actual_win_rate",
            "model_prob_final": "model_predicted_win_rate",
        }, inplace=True)
        
        # Compute recovery premium
        recovery["recovery_premium"] = recovery["actual_win_rate"] - recovery["model_predicted_win_rate"]
        
        self.log.info("recovery_analysis_complete", num_phases=len(recovery))
        
        return recovery

