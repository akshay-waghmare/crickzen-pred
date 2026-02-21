"""
OOF Calibration Analyzer

Comprehensive out-of-fold analysis comparing multiple calibration strategies.
Generates detailed metrics breakdown by innings, phase, and overall.
"""

import pandas as pd
import numpy as np
import joblib
from pathlib import Path
from sklearn.model_selection import KFold
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, brier_score_loss
from typing import Dict, List, Tuple
import structlog

logger = structlog.get_logger()


def calculate_ece(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> float:
    """Calculate Expected Calibration Error."""
    y_prob = np.clip(y_prob, 0, 1)
    ece = 0.0
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    
    for i in range(n_bins):
        if i == n_bins - 1:
            mask = (y_prob >= bin_boundaries[i]) & (y_prob <= bin_boundaries[i + 1])
        else:
            mask = (y_prob >= bin_boundaries[i]) & (y_prob < bin_boundaries[i + 1])
        
        if mask.sum() > 0:
            accuracy = y_true[mask].mean()
            avg_prob = y_prob[mask].mean()
            ece += mask.mean() * abs(avg_prob - accuracy)
    
    return ece


def brier_score(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """Calculate Brier score."""
    y_prob = np.clip(y_prob, 0, 1)
    return np.mean((y_prob - y_true) ** 2)


def safe_log_loss(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    """
    Calculate log loss (cross-entropy) with confidence clipping.
    
    Using clip=0.01 (betting/forecasting standard) instead of eps=1e-15
    to prevent extreme tail predictions from dominating the metric.
    This penalizes overconfident incorrect predictions appropriately.
    
    Uses manual calculation to match standalone analysis scripts.
    """
    y_prob = np.clip(y_prob, 0.01, 0.99)
    loss = -(y_true * np.log(y_prob) + (1 - y_true) * np.log(1 - y_prob))
    return float(np.mean(loss))


class OOFAnalyzer:
    """Comprehensive OOF calibration analyzer."""
    
    def __init__(self, model, X: pd.DataFrame, y: np.ndarray, 
                 innings: np.ndarray = None, over: np.ndarray = None, 
                 resource_win_prob: np.ndarray = None,
                 n_splits: int = 5, total_overs: int = 20):
        """
        Initialize analyzer.
        
        Args:
            model: Base model to analyze (will be cloned for each fold)
            X: Feature matrix
            y: Target values
            innings: Innings indicator (1 or 2), optional
            over: Over number (1-total_overs), optional
            resource_win_prob: Resource-based win probability feature, optional
            n_splits: Number of folds for cross-validation
            total_overs: Total overs in format (20 for T20, 50 for ODI)
        """
        self.model = model
        self.X = X
        self.y = y
        self.innings = innings
        self.over = over
        self.resource_win_prob = resource_win_prob
        self.n_splits = n_splits
        self.total_overs = total_overs
        
        # Determine phase names and boundaries based on format
        if total_overs > 20:
            # ODI format: 4 phases
            self.phase_names = ['powerplay', 'middle', 'setup', 'death']
            self.phase_boundaries = {
                'powerplay': (1, 10),
                'middle': (11, 34),
                'setup': (35, 40),
                'death': (41, total_overs),
            }
        else:
            # T20 format: 3 phases
            self.phase_names = ['powerplay', 'middle', 'death']
            self.phase_boundaries = {
                'powerplay': (1, 6),
                'middle': (7, 15),
                'death': (16, total_overs),
            }
        
        # Calculate phases if over is provided
        if over is not None:
            self.phases = self._calculate_phases(over)
        else:
            self.phases = None
    
    def _calculate_phases(self, over: np.ndarray) -> np.ndarray:
        """Calculate phase from over number based on format."""
        phases = np.empty(len(over), dtype='U10')
        for phase_name, (start, end) in self.phase_boundaries.items():
            mask = (over >= start) & (over <= end)
            phases[mask] = phase_name
        return phases
    
    def generate_oof_predictions(self) -> np.ndarray:
        """Generate out-of-fold predictions."""
        from sklearn.base import clone
        
        oof_probs = np.zeros(len(self.y))
        kf = KFold(n_splits=self.n_splits, shuffle=False)
        
        logger.info('Generating OOF predictions', n_splits=self.n_splits, samples=len(self.X))
        
        for fold_idx, (train_idx, val_idx) in enumerate(kf.split(self.X), 1):
            fold_model = clone(self.model)
            X_train = self.X.iloc[train_idx] if isinstance(self.X, pd.DataFrame) else self.X[train_idx]
            X_val = self.X.iloc[val_idx] if isinstance(self.X, pd.DataFrame) else self.X[val_idx]
            y_train = self.y[train_idx]
            
            fold_model.fit(X_train, y_train)
            oof_probs[val_idx] = fold_model.predict_proba(X_val)[:, 1]
            
            logger.info(f'Fold {fold_idx} complete', train_size=len(train_idx), val_size=len(val_idx))
        
        return oof_probs
    
    def train_calibrators(self, oof_probs: np.ndarray) -> Dict:
        """Train all calibration strategies."""
        calibrators = {}
        
        # 1. Combined (single isotonic)
        logger.info('Training Combined calibrator (single isotonic)')
        iso_combined = IsotonicRegression(out_of_bounds='clip')
        iso_combined.fit(oof_probs, self.y)
        calibrators['combined'] = iso_combined
        
        # 2. Innings-specific (if innings available)
        if self.innings is not None:
            logger.info('Training Innings-Specific calibrators')
            calibrators['innings_specific'] = {}
            for inn in [1, 2]:
                mask = self.innings == inn
                if mask.sum() > 50:
                    iso = IsotonicRegression(out_of_bounds='clip')
                    iso.fit(oof_probs[mask], self.y[mask])
                    calibrators['innings_specific'][inn] = iso
        
        # 3. Innings×Phase (if innings and over available)
        if self.innings is not None and self.phases is not None:
            logger.info('Training Innings×Phase calibrators')
            calibrators['innings_phase'] = {}
            for inn in [1, 2]:
                for phase in self.phase_names:
                    mask = (self.innings == inn) & (self.phases == phase)
                    if mask.sum() > 50:
                        iso = IsotonicRegression(out_of_bounds='clip')
                        iso.fit(oof_probs[mask], self.y[mask])
                        calibrators['innings_phase'][f'inn{inn}_{phase}'] = iso
        
        # 4. Brier-Optimized (per-over if over available)
        if self.innings is not None and self.over is not None:
            logger.info('Training Brier-Optimized calibrators (per-over)')
            calibrators['brier_optimized'] = {}
            for inn in [1, 2]:
                for ov in range(1, self.total_overs + 1):
                    mask = (self.innings == inn) & (self.over == ov)
                    if mask.sum() > 30:
                        iso = IsotonicRegression(out_of_bounds='clip')
                        iso.fit(oof_probs[mask], self.y[mask])
                        calibrators['brier_optimized'][f'inn{inn}_over{ov}'] = iso
        
        # 5. ECE-Optimized (histogram binning per innings×phase)
        if self.innings is not None and self.phases is not None:
            logger.info('Training ECE-Optimized calibrators (histogram binning)')
            calibrators['ece_optimized'] = {}
            n_bins = 15
            for inn in [1, 2]:
                for phase in self.phase_names:
                    mask = (self.innings == inn) & (self.phases == phase)
                    if mask.sum() > 50:
                        probs = oof_probs[mask]
                        targets = self.y[mask]
                        
                        # Histogram binning
                        bin_boundaries = np.linspace(0, 1, n_bins + 1)
                        bin_means = []
                        bin_centers = []
                        
                        for i in range(n_bins):
                            if i == n_bins - 1:
                                bin_mask = (probs >= bin_boundaries[i]) & (probs <= bin_boundaries[i + 1])
                            else:
                                bin_mask = (probs >= bin_boundaries[i]) & (probs < bin_boundaries[i + 1])
                            
                            if bin_mask.sum() > 0:
                                bin_means.append(targets[bin_mask].mean())
                                bin_centers.append(probs[bin_mask].mean())
                            else:
                                bin_means.append((bin_boundaries[i] + bin_boundaries[i + 1]) / 2)
                                bin_centers.append((bin_boundaries[i] + bin_boundaries[i + 1]) / 2)
                        
                        # Fit isotonic on bin statistics
                        iso = IsotonicRegression(out_of_bounds='clip')
                        iso.fit(np.array(bin_centers), np.array(bin_means))
                        calibrators['ece_optimized'][f'inn{inn}_{phase}'] = iso
        
        # 6. LogLoss-Optimized (Platt scaling per innings×phase)
        if self.innings is not None and self.phases is not None:
            logger.info('Training LogLoss-Optimized calibrators (Platt scaling)')
            calibrators['logloss_optimized'] = {}
            for inn in [1, 2]:
                for phase in self.phase_names:
                    mask = (self.innings == inn) & (self.phases == phase)
                    if mask.sum() > 50:
                        platt = LogisticRegression(C=1e10, solver='lbfgs', max_iter=1000)
                        platt.fit(oof_probs[mask].reshape(-1, 1), self.y[mask])
                        calibrators['logloss_optimized'][f'inn{inn}_{phase}'] = platt
        
        return calibrators
    
    def apply_calibrators(self, oof_probs: np.ndarray, calibrators: Dict) -> Dict[str, np.ndarray]:
        """Apply all calibrators to OOF predictions."""
        calibrated_probs = {'raw': oof_probs.copy()}
        
        # Combined
        if 'combined' in calibrators:
            calibrated_probs['combined'] = calibrators['combined'].predict(oof_probs)
        
        # Innings-specific
        if 'innings_specific' in calibrators and self.innings is not None:
            probs = oof_probs.copy()
            for inn, cal in calibrators['innings_specific'].items():
                mask = self.innings == inn
                probs[mask] = cal.predict(oof_probs[mask])
            calibrated_probs['innings_specific'] = probs
        
        # Innings×Phase
        if 'innings_phase' in calibrators and self.innings is not None and self.phases is not None:
            probs = oof_probs.copy()
            for inn in [1, 2]:
                for phase in self.phase_names:
                    key = f'inn{inn}_{phase}'
                    if key in calibrators['innings_phase']:
                        mask = (self.innings == inn) & (self.phases == phase)
                        probs[mask] = calibrators['innings_phase'][key].predict(oof_probs[mask])
            calibrated_probs['innings_phase'] = probs
        
        # Brier-Optimized
        if 'brier_optimized' in calibrators and self.innings is not None and self.over is not None:
            probs = oof_probs.copy()
            for inn in [1, 2]:
                for ov in range(1, self.total_overs + 1):
                    key = f'inn{inn}_over{ov}'
                    if key in calibrators['brier_optimized']:
                        mask = (self.innings == inn) & (self.over == ov)
                        probs[mask] = calibrators['brier_optimized'][key].predict(oof_probs[mask])
            calibrated_probs['brier_optimized'] = probs
        
        # ECE-Optimized
        if 'ece_optimized' in calibrators and self.innings is not None and self.phases is not None:
            probs = oof_probs.copy()
            for inn in [1, 2]:
                for phase in self.phase_names:
                    key = f'inn{inn}_{phase}'
                    if key in calibrators['ece_optimized']:
                        mask = (self.innings == inn) & (self.phases == phase)
                        probs[mask] = calibrators['ece_optimized'][key].predict(oof_probs[mask])
            calibrated_probs['ece_optimized'] = probs
        
        # LogLoss-Optimized
        if 'logloss_optimized' in calibrators and self.innings is not None and self.phases is not None:
            probs = oof_probs.copy()
            for inn in [1, 2]:
                for phase in self.phase_names:
                    key = f'inn{inn}_{phase}'
                    if key in calibrators['logloss_optimized']:
                        mask = (self.innings == inn) & (self.phases == phase)
                        platt = calibrators['logloss_optimized'][key]
                        probs[mask] = platt.predict_proba(oof_probs[mask].reshape(-1, 1))[:, 1]
            calibrated_probs['logloss_optimized'] = probs
        
        return calibrated_probs
    
    def calculate_metrics(self, calibrated_probs: Dict[str, np.ndarray]) -> pd.DataFrame:
        """Calculate metrics for all calibrators."""
        results = []
        
        for method, probs in calibrated_probs.items():
            # Overall metrics
            row = {
                'method': method,
                'segment': 'overall',
                'brier': brier_score(self.y, probs),
                'ece': calculate_ece(self.y, probs),
                'logloss': safe_log_loss(self.y, probs),
                'n_samples': len(self.y)
            }
            results.append(row)
            
            # Per-innings metrics
            if self.innings is not None:
                for inn in [1, 2]:
                    mask = self.innings == inn
                    if mask.sum() > 0:
                        row = {
                            'method': method,
                            'segment': f'innings_{inn}',
                            'brier': brier_score(self.y[mask], probs[mask]),
                            'ece': calculate_ece(self.y[mask], probs[mask]),
                            'logloss': safe_log_loss(self.y[mask], probs[mask]),
                            'n_samples': int(mask.sum())
                        }
                        results.append(row)
            
            # Per-innings×phase metrics
            if self.innings is not None and self.phases is not None:
                for inn in [1, 2]:
                    for phase in self.phase_names:
                        mask = (self.innings == inn) & (self.phases == phase)
                        if mask.sum() > 0:
                            row = {
                                'method': method,
                                'segment': f'inn{inn}_{phase}',
                                'brier': brier_score(self.y[mask], probs[mask]),
                                'ece': calculate_ece(self.y[mask], probs[mask]),
                                'logloss': safe_log_loss(self.y[mask], probs[mask]),
                                'n_samples': int(mask.sum())
                            }
                            results.append(row)
        
        return pd.DataFrame(results)
    
    def analyze_probability_bins(self, calibrated_probs: Dict[str, np.ndarray], 
                                  n_bins: int = 10) -> pd.DataFrame:
        """
        Analyze calibration quality across probability bins.
        
        Args:
            calibrated_probs: Dict of method -> calibrated probabilities
            n_bins: Number of probability bins
            
        Returns:
            DataFrame with bin-level metrics for each method
        """
        results = []
        bin_edges = np.linspace(0, 1, n_bins + 1)
        
        for method, probs in calibrated_probs.items():
            for i in range(n_bins):
                low, high = bin_edges[i], bin_edges[i + 1]
                if i == n_bins - 1:
                    mask = (probs >= low) & (probs <= high)
                else:
                    mask = (probs >= low) & (probs < high)
                
                n = mask.sum()
                if n > 0:
                    mean_pred = probs[mask].mean()
                    mean_actual = self.y[mask].mean()
                    calibration_error = abs(mean_pred - mean_actual)
                    brier = ((probs[mask] - self.y[mask]) ** 2).mean()
                    
                    results.append({
                        'method': method,
                        'bin': f'{low:.1f}-{high:.1f}',
                        'bin_low': low,
                        'bin_high': high,
                        'n_samples': int(n),
                        'mean_predicted': mean_pred,
                        'mean_actual': mean_actual,
                        'calibration_error': calibration_error,
                        'brier': brier
                    })
        
        return pd.DataFrame(results)
    
    def analyze_resource_win_prob(self, calibrated_probs: Dict[str, np.ndarray]) -> pd.DataFrame:
        """
        Analyze model predictions vs resource_win_prob baseline.
        
        Compares the calibrated model predictions against the resource-based
        win probability feature to quantify model improvement.
        
        Returns:
            DataFrame with comparison metrics
        """
        if self.resource_win_prob is None:
            logger.warning('resource_win_prob not provided, skipping analysis')
            return pd.DataFrame()
        
        results = []
        
        # Resource win prob baseline metrics
        rwp_brier = brier_score(self.y, self.resource_win_prob)
        rwp_ece = calculate_ece(self.y, self.resource_win_prob)
        rwp_logloss = safe_log_loss(self.y, self.resource_win_prob)
        
        results.append({
            'method': 'resource_win_prob',
            'segment': 'overall',
            'brier': rwp_brier,
            'ece': rwp_ece,
            'logloss': rwp_logloss,
            'n_samples': len(self.y)
        })
        
        # Per-innings
        if self.innings is not None:
            for inn in [1, 2]:
                mask = self.innings == inn
                if mask.sum() > 0:
                    results.append({
                        'method': 'resource_win_prob',
                        'segment': f'innings_{inn}',
                        'brier': brier_score(self.y[mask], self.resource_win_prob[mask]),
                        'ece': calculate_ece(self.y[mask], self.resource_win_prob[mask]),
                        'logloss': safe_log_loss(self.y[mask], self.resource_win_prob[mask]),
                        'n_samples': int(mask.sum())
                    })
        
        # Per-innings×phase
        if self.innings is not None and self.phases is not None:
            for inn in [1, 2]:
                for phase in self.phase_names:
                    mask = (self.innings == inn) & (self.phases == phase)
                    if mask.sum() > 0:
                        results.append({
                            'method': 'resource_win_prob',
                            'segment': f'inn{inn}_{phase}',
                            'brier': brier_score(self.y[mask], self.resource_win_prob[mask]),
                            'ece': calculate_ece(self.y[mask], self.resource_win_prob[mask]),
                            'logloss': safe_log_loss(self.y[mask], self.resource_win_prob[mask]),
                            'n_samples': int(mask.sum())
                        })
        
        return pd.DataFrame(results)
    
    def run_analysis(self, output_dir: Path = None) -> Tuple[Dict, pd.DataFrame]:
        """
        Run complete OOF calibration analysis.
        
        Returns:
            calibrators: Dict of trained calibrators
            results_df: DataFrame with detailed metrics
        """
        logger.info('Starting OOF calibration analysis')
        
        # Generate OOF predictions
        oof_probs = self.generate_oof_predictions()
        
        # Train calibrators
        calibrators = self.train_calibrators(oof_probs)
        
        # Apply calibrators
        calibrated_probs = self.apply_calibrators(oof_probs, calibrators)
        
        # Calculate metrics
        results_df = self.calculate_metrics(calibrated_probs)
        
        # Add resource_win_prob baseline if available
        if self.resource_win_prob is not None:
            resource_df = self.analyze_resource_win_prob(calibrated_probs)
            if not resource_df.empty:
                results_df = pd.concat([results_df, resource_df], ignore_index=True)
                logger.info('Added resource_win_prob baseline comparison')
        
        # Calculate probability bin analysis
        prob_bins_df = self.analyze_probability_bins(calibrated_probs)
        
        # Save results if output_dir provided
        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Save detailed results
            results_df.to_csv(output_dir / 'oof_calibration_results.csv', index=False)
            logger.info('Saved detailed results', path=str(output_dir / 'oof_calibration_results.csv'))
            
            # Save probability bin analysis
            prob_bins_df.to_csv(output_dir / 'oof_probability_bins.csv', index=False)
            logger.info('Saved probability bin analysis', path=str(output_dir / 'oof_probability_bins.csv'))
            
            # Save calibrators
            calibrators_path = output_dir / 'oof_calibrators.pkl'
            joblib.dump(calibrators, calibrators_path)
            logger.info('Saved calibrators', path=str(calibrators_path))
            
            # Generate summary report
            self._generate_report(results_df, prob_bins_df, output_dir)
        
        logger.info('OOF analysis complete')
        
        return calibrators, results_df
    
    def _generate_report(self, results_df: pd.DataFrame, prob_bins_df: pd.DataFrame, output_dir: Path):
        """Generate markdown report."""
        report_lines = [
            "# OOF Calibration Analysis Report",
            f"\n**Generated:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Samples:** {len(self.y):,}",
            f"**Folds:** {self.n_splits}",
            "\n---\n",
            "## Overall Performance\n"
        ]
        
        # Helper function for markdown tables without tabulate dependency
        def df_to_markdown_simple(df):
            """Simple markdown table without tabulate dependency"""
            lines = []
            # Header
            header = "| " + " | ".join(str(c) for c in df.columns) + " |"
            lines.append(header)
            # Separator
            sep = "| " + " | ".join(["---" for _ in df.columns]) + " |"
            lines.append(sep)
            # Rows
            for _, row in df.iterrows():
                row_str = "| " + " | ".join([
                    f"{val:.4f}" if isinstance(val, (int, float)) and not isinstance(val, bool) else str(val)
                    for val in row
                ]) + " |"
                lines.append(row_str)
            return "\n".join(lines)
        
        # Overall table
        overall = results_df[results_df['segment'] == 'overall'].copy()
        overall = overall.sort_values('brier')
        overall_table = df_to_markdown_simple(overall[['method', 'brier', 'ece', 'logloss']])
        report_lines.append(overall_table)
        
        # Per-innings breakdown
        if self.innings is not None:
            report_lines.append("\n\n## Per-Innings Breakdown\n")
            for inn in [1, 2]:
                segment = f'innings_{inn}'
                inn_df = results_df[results_df['segment'] == segment].copy()
                if not inn_df.empty:
                    inn_df = inn_df.sort_values('brier')
                    report_lines.append(f"\n### Innings {inn}\n")
                    inn_table = df_to_markdown_simple(inn_df[['method', 'brier', 'ece', 'logloss', 'n_samples']])
                    report_lines.append(inn_table)
        
        # Per-phase breakdown
        if self.innings is not None and self.phases is not None:
            report_lines.append("\n\n## Per-Innings × Phase Breakdown\n")
            for inn in [1, 2]:
                for phase in self.phase_names:
                    segment = f'inn{inn}_{phase}'
                    phase_df = results_df[results_df['segment'] == segment].copy()
                    if not phase_df.empty:
                        phase_df = phase_df.sort_values('brier')
                        report_lines.append(f"\n### Innings {inn} - {phase.title()}\n")
                        phase_table = df_to_markdown_simple(phase_df[['method', 'brier', 'ece', 'logloss', 'n_samples']])
                        report_lines.append(phase_table)
        
        # Best Method by Segment Summary
        report_lines.append("\n\n## Best Method by Segment\n")
        report_lines.append("This section shows which calibration method performs best for each segment, broken down by metric.\n")
        
        # Build best method summary for each metric
        for metric in ['brier', 'ece', 'logloss']:
            metric_display = {'brier': 'Brier Score', 'ece': 'ECE', 'logloss': 'LogLoss'}[metric]
            report_lines.append(f"\n### Best by {metric_display}\n")
            
            summary_rows = []
            
            # Overall
            overall_df = results_df[results_df['segment'] == 'overall']
            if not overall_df.empty:
                best = overall_df.loc[overall_df[metric].idxmin()]
                summary_rows.append({
                    'Segment': 'Overall',
                    'Best Method': best['method'],
                    metric_display: f"{best[metric]:.4f}"
                })
            
            # Per-innings
            if self.innings is not None:
                for inn in [1, 2]:
                    segment = f'innings_{inn}'
                    seg_df = results_df[results_df['segment'] == segment]
                    if not seg_df.empty:
                        best = seg_df.loc[seg_df[metric].idxmin()]
                        summary_rows.append({
                            'Segment': f'Innings {inn}',
                            'Best Method': best['method'],
                            metric_display: f"{best[metric]:.4f}"
                        })
            
            # Per-innings×phase
            if self.innings is not None and self.phases is not None:
                for inn in [1, 2]:
                    for phase in self.phase_names:
                        segment = f'inn{inn}_{phase}'
                        seg_df = results_df[results_df['segment'] == segment]
                        if not seg_df.empty:
                            best = seg_df.loc[seg_df[metric].idxmin()]
                            summary_rows.append({
                                'Segment': f'Inn{inn} {phase.title()}',
                                'Best Method': best['method'],
                                metric_display: f"{best[metric]:.4f}"
                            })
            
            if summary_rows:
                summary_df = pd.DataFrame(summary_rows)
                summary_table = df_to_markdown_simple(summary_df)
                report_lines.append(summary_table)
        
        # Recommendation summary
        report_lines.append("\n\n## Recommendations\n")
        report_lines.append("Based on the analysis above:\n")
        
        # Count wins per method per metric
        metric_winners = {}
        for metric in ['brier', 'ece', 'logloss']:
            segments = ['overall'] + [f'innings_{inn}' for inn in [1, 2]]
            if self.innings is not None and self.phases is not None:
                segments += [f'inn{inn}_{phase}' for inn in [1, 2] for phase in self.phase_names]
            
            wins = {}
            for segment in segments:
                seg_df = results_df[results_df['segment'] == segment]
                if not seg_df.empty:
                    best_method = seg_df.loc[seg_df[metric].idxmin(), 'method']
                    wins[best_method] = wins.get(best_method, 0) + 1
            metric_winners[metric] = wins
        
        metric_display = {'brier': 'Brier Score', 'ece': 'ECE', 'logloss': 'LogLoss'}
        for metric, wins in metric_winners.items():
            if wins:
                top_method = max(wins.keys(), key=lambda m: wins[m])
                report_lines.append(f"- **{metric_display[metric]}**: `{top_method}` wins in {wins[top_method]} segments")
        
        # Add resource_win_prob comparison if available
        if self.resource_win_prob is not None:
            report_lines.append("\n\n## Resource Win Prob Baseline Comparison\n")
            report_lines.append("Comparing model predictions vs the `resource_win_prob` feature (DLS-based baseline):\n")
            
            rwp_results = results_df[results_df['method'] == 'resource_win_prob']
            if not rwp_results.empty:
                # Overall comparison
                rwp_overall = rwp_results[rwp_results['segment'] == 'overall']
                if not rwp_overall.empty:
                    rwp_brier = rwp_overall['brier'].values[0]
                    rwp_logloss = rwp_overall['logloss'].values[0]
                    
                    # Get best model metrics
                    model_methods = [m for m in results_df['method'].unique() if m != 'resource_win_prob']
                    overall_df = results_df[(results_df['segment'] == 'overall') & (results_df['method'].isin(model_methods))]
                    
                    if not overall_df.empty:
                        best_brier_method = overall_df.loc[overall_df['brier'].idxmin()]
                        best_logloss_method = overall_df.loc[overall_df['logloss'].idxmin()]
                        
                        brier_improvement = (rwp_brier - best_brier_method['brier']) / rwp_brier * 100
                        logloss_improvement = (rwp_logloss - best_logloss_method['logloss']) / rwp_logloss * 100
                        
                        report_lines.append(f"\n| Metric | resource_win_prob | Best Model | Improvement |")
                        report_lines.append(f"| --- | --- | --- | --- |")
                        report_lines.append(f"| Brier | {rwp_brier:.4f} | {best_brier_method['brier']:.4f} ({best_brier_method['method']}) | **{brier_improvement:+.1f}%** |")
                        report_lines.append(f"| LogLoss | {rwp_logloss:.4f} | {best_logloss_method['logloss']:.4f} ({best_logloss_method['method']}) | **{logloss_improvement:+.1f}%** |")
        
        # Add probability bin analysis
        if not prob_bins_df.empty:
            report_lines.append("\n\n## Probability Bin Calibration Analysis\n")
            report_lines.append("Calibration quality by predicted probability range (10 bins):\n")
            
            # Show for key methods: raw, brier_optimized, innings_phase
            key_methods = ['raw', 'brier_optimized', 'innings_phase']
            available_methods = [m for m in key_methods if m in prob_bins_df['method'].unique()]
            
            for method in available_methods:
                method_bins = prob_bins_df[prob_bins_df['method'] == method].copy()
                if not method_bins.empty:
                    report_lines.append(f"\n### {method}\n")
                    report_lines.append("| Bin | N | Mean Pred | Mean Actual | Cal Error | Brier |")
                    report_lines.append("| --- | --- | --- | --- | --- | --- |")
                    
                    for _, row in method_bins.iterrows():
                        ce_flag = "⚠️" if row['calibration_error'] > 0.05 else ""
                        report_lines.append(
                            f"| {row['bin']} | {row['n_samples']:,} | {row['mean_predicted']:.3f} | "
                            f"{row['mean_actual']:.3f} | {row['calibration_error']:.4f} {ce_flag} | {row['brier']:.4f} |"
                        )
            
            # Add problematic bins summary
            report_lines.append("\n### Problematic Bins (Calibration Error > 0.05)\n")
            for method in available_methods:
                method_bins = prob_bins_df[prob_bins_df['method'] == method]
                problems = method_bins[method_bins['calibration_error'] > 0.05]
                if len(problems) > 0:
                    report_lines.append(f"\n**{method}:**")
                    for _, row in problems.iterrows():
                        direction = "over-predicting" if row['mean_predicted'] > row['mean_actual'] else "under-predicting"
                        report_lines.append(f"- Bin {row['bin']}: CE={row['calibration_error']:.4f} ({direction})")
                else:
                    report_lines.append(f"\n**{method}:** ✅ All bins have CE ≤ 0.05")
        
        # Add ECE warning
        report_lines.append("\n\n## Important Note on ECE = 0.0000\n")
        report_lines.append("""
ECE values of exactly 0.0000 for isotonic-calibrated methods are **mathematically expected**, not a bug:

**Root Cause:**
- Isotonic regression ensures: `E[Y | P_calibrated = p] = p` by construction
- ECE measures: `|E[Y in bin] - E[P_calibrated in bin]|`  
- After isotonic calibration: `E[Y] = E[P]` within each bin BY DESIGN
- This makes ECE = 0 a **tautology**, not an empirical measurement

**Interpretation:**
- ECE = 0 does NOT mean the calibrator is "perfect"
- It means ECE is measuring the calibrator's own constraint
- This is true for: `brier_optimized`, `innings_phase`, `innings_specific`, `combined`

**Recommended Decision Metrics:**
1. **Brier Score** (primary) - Measures accuracy + calibration together
2. **LogLoss** - Measures probabilistic sharpness  
3. **ECE** - Only meaningful for `raw` (uncalibrated) model comparison

For production, use **Brier Score** as the primary selection criterion.
""")
        
        # Write report
        report_path = output_dir / 'OOF_CALIBRATION_REPORT.md'
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report_lines))
        
        logger.info('Generated markdown report', path=str(report_path))
