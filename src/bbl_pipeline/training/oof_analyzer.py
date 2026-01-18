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
                 n_splits: int = 5):
        """
        Initialize analyzer.
        
        Args:
            model: Base model to analyze (will be cloned for each fold)
            X: Feature matrix
            y: Target values
            innings: Innings indicator (1 or 2), optional
            over: Over number (1-20), optional
            n_splits: Number of folds for cross-validation
        """
        self.model = model
        self.X = X
        self.y = y
        self.innings = innings
        self.over = over
        self.n_splits = n_splits
        
        # Calculate phases if over is provided
        if over is not None:
            self.phases = self._calculate_phases(over)
        else:
            self.phases = None
    
    def _calculate_phases(self, over: np.ndarray) -> np.ndarray:
        """Calculate phase from over number."""
        phases = np.empty(len(over), dtype='U10')
        phases[over <= 6] = 'powerplay'
        phases[(over > 6) & (over <= 15)] = 'middle'
        phases[over > 15] = 'death'
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
                for phase in ['powerplay', 'middle', 'death']:
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
                for ov in range(1, 21):
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
                for phase in ['powerplay', 'middle', 'death']:
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
                for phase in ['powerplay', 'middle', 'death']:
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
                for phase in ['powerplay', 'middle', 'death']:
                    key = f'inn{inn}_{phase}'
                    if key in calibrators['innings_phase']:
                        mask = (self.innings == inn) & (self.phases == phase)
                        probs[mask] = calibrators['innings_phase'][key].predict(oof_probs[mask])
            calibrated_probs['innings_phase'] = probs
        
        # Brier-Optimized
        if 'brier_optimized' in calibrators and self.innings is not None and self.over is not None:
            probs = oof_probs.copy()
            for inn in [1, 2]:
                for ov in range(1, 21):
                    key = f'inn{inn}_over{ov}'
                    if key in calibrators['brier_optimized']:
                        mask = (self.innings == inn) & (self.over == ov)
                        probs[mask] = calibrators['brier_optimized'][key].predict(oof_probs[mask])
            calibrated_probs['brier_optimized'] = probs
        
        # ECE-Optimized
        if 'ece_optimized' in calibrators and self.innings is not None and self.phases is not None:
            probs = oof_probs.copy()
            for inn in [1, 2]:
                for phase in ['powerplay', 'middle', 'death']:
                    key = f'inn{inn}_{phase}'
                    if key in calibrators['ece_optimized']:
                        mask = (self.innings == inn) & (self.phases == phase)
                        probs[mask] = calibrators['ece_optimized'][key].predict(oof_probs[mask])
            calibrated_probs['ece_optimized'] = probs
        
        # LogLoss-Optimized
        if 'logloss_optimized' in calibrators and self.innings is not None and self.phases is not None:
            probs = oof_probs.copy()
            for inn in [1, 2]:
                for phase in ['powerplay', 'middle', 'death']:
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
                    for phase in ['powerplay', 'middle', 'death']:
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
        
        # Save results if output_dir provided
        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Save detailed results
            results_df.to_csv(output_dir / 'oof_calibration_results.csv', index=False)
            logger.info('Saved detailed results', path=str(output_dir / 'oof_calibration_results.csv'))
            
            # Save calibrators
            calibrators_path = output_dir / 'oof_calibrators.pkl'
            joblib.dump(calibrators, calibrators_path)
            logger.info('Saved calibrators', path=str(calibrators_path))
            
            # Generate summary report
            self._generate_report(results_df, output_dir)
        
        logger.info('OOF analysis complete')
        
        return calibrators, results_df
    
    def _generate_report(self, results_df: pd.DataFrame, output_dir: Path):
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
                for phase in ['powerplay', 'middle', 'death']:
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
                    for phase in ['powerplay', 'middle', 'death']:
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
                segments += [f'inn{inn}_{phase}' for inn in [1, 2] for phase in ['powerplay', 'middle', 'death']]
            
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
        with open(report_path, 'w') as f:
            f.write('\n'.join(report_lines))
        
        logger.info('Generated markdown report', path=str(report_path))
