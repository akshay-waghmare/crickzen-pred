from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import joblib
import numpy as np
import pandas as pd


@dataclass
class OddsDirectionModel:
    model_dir: Path | None = None
    status: str = 'unavailable'
    models: Dict[str, Any] | None = None
    feature_columns: List[str] | None = None
    training_manifest: Dict[str, Any] | None = None

    @classmethod
    def load(cls, model_dir: str | Path | None) -> 'OddsDirectionModel':
        path = Path(model_dir) if model_dir else None
        if not path or not path.exists():
            return cls(model_dir=path, status='unavailable')

        try:
            models = joblib.load(path / 'champion_model.joblib')
            with open(path / 'feature_columns.json', 'r', encoding='utf-8') as handle:
                feature_columns = json.load(handle)
            with open(path / 'training_manifest.json', 'r', encoding='utf-8') as handle:
                training_manifest = json.load(handle)
            return cls(
                model_dir=path,
                status='ready',
                models=models,
                feature_columns=feature_columns,
                training_manifest=training_manifest,
            )
        except Exception as exc:
            return cls(model_dir=path, status=f'load_error: {exc}')

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            if isinstance(value, str) and not value.strip():
                return default
            result = float(value)
            if np.isnan(result):
                return default
            return result
        except Exception:
            return default

    @staticmethod
    def _phase_name(features: Dict[str, Any]) -> str:
        if OddsDirectionModel._safe_float(features.get('is_powerplay')) >= 0.5:
            return 'powerplay'
        if OddsDirectionModel._safe_float(features.get('is_death_overs')) >= 0.5:
            return 'death'
        return 'middle'

    @staticmethod
    def _dedupe_history(history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        deduped: List[Dict[str, Any]] = []
        seen: set[tuple[Any, Any, Any]] = set()
        for entry in reversed(history):
            key = (entry.get('innings'), entry.get('over'), entry.get('ball'))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(entry)
        deduped.reverse()
        return deduped

    def _phase_adjustment(self, phase_name: str) -> float:
        manifest = self.training_manifest or {}
        adjustments = manifest.get('interval_conformal_adjustments', {'overall': 0.0})
        return self._safe_float(adjustments.get(phase_name, adjustments.get('overall', 0.0)))

    def _league_indicator_updates(self, row: Dict[str, float], league: str | None) -> None:
        league_code = (league or '').lower()
        for column in self.feature_columns or []:
            if not column.startswith('league_'):
                continue
            row[column] = 1.0 if column == f'league_{league_code}' else 0.0

    def _phase_indicator_updates(self, row: Dict[str, float], phase_name: str) -> None:
        for column in self.feature_columns or []:
            if not column.startswith('phase_'):
                continue
            row[column] = 1.0 if column == f'phase_{phase_name}' else 0.0

    def _build_feature_row(
        self,
        *,
        live_features: Dict[str, Any],
        predictor: Any,
        batting_team: str,
        venue: str,
        league: str | None,
        innings: int,
        over: int,
        ball: int,
        target_score: int | None,
        current_ml_prob: float,
        history: List[Dict[str, Any]],
    ) -> Dict[str, float]:
        row = {key: self._safe_float(value) for key, value in live_features.items()}
        row['innings'] = float(innings)
        row['over'] = float(over)
        row['ball'] = float(ball)
        row['ball_number'] = float(over * 6 + ball)
        row['ml_prob'] = current_ml_prob

        deduped_history = self._dedupe_history(history)
        raw_history = [self._safe_float(item.get('raw_win_prob', item.get('bat_prob'))) for item in deduped_history]
        resource_history = [self._safe_float(item.get('resource_win_prob', 0.0)) for item in deduped_history]

        past_6 = raw_history[-6] if len(raw_history) >= 6 else current_ml_prob
        past_12 = raw_history[-12] if len(raw_history) >= 12 else current_ml_prob
        row['ml_prob_delta_6'] = current_ml_prob - past_6
        row['ml_prob_delta_12'] = current_ml_prob - past_12
        row['momentum_baseline_12'] = current_ml_prob - past_12

        resource_wp = self._safe_float(row.get('resource_win_prob'), 0.5)
        row['ml_rwp_gap'] = current_ml_prob - resource_wp
        past_gap_6 = (raw_history[-6] - resource_history[-6]) if len(raw_history) >= 6 and len(resource_history) >= 6 else row['ml_rwp_gap']
        row['ml_rwp_gap_delta_6'] = row['ml_rwp_gap'] - past_gap_6

        total_overs = self._safe_float(getattr(getattr(predictor, 'format_config', None), 'total_overs', 20), 20.0)
        total_overs = total_overs if total_overs > 0 else 20.0
        venue_stats = predictor.feature_store.get_venue_stats(venue) if predictor and getattr(predictor, 'feature_store', None) else None
        team_stats = predictor.feature_store.get_team_stats(batting_team) if predictor and getattr(predictor, 'feature_store', None) else None
        venue_stats = venue_stats or {}
        team_stats = team_stats or {}

        venue_avg_score = self._safe_float(venue_stats.get('venue_avg_score'), self._safe_float(getattr(getattr(predictor, 'format_config', None), 'par_score', 165.0), 165.0))
        team_avg_score = self._safe_float(team_stats.get('avg_score'), venue_avg_score)
        team_venue_avg_score = (team_avg_score + venue_avg_score) / 2.0
        team_high_score = max(team_avg_score, venue_avg_score)
        team_venue_high_score = max(team_venue_avg_score, team_high_score)
        venue_avg_rr = venue_avg_score / total_overs
        team_avg_rr = team_avg_score / total_overs
        team_venue_avg_rr = team_venue_avg_score / total_overs
        team_high_rr = team_high_score / total_overs
        team_venue_high_rr = team_venue_high_score / total_overs
        current_rr = self._safe_float(row.get('current_run_rate'))
        projected_score = self._safe_float(row.get('projected_score'), venue_avg_score)

        row['venue_avg_innings_score'] = venue_avg_score
        row['batting_team_avg_innings_score'] = team_avg_score
        row['batting_team_venue_avg_innings_score'] = team_venue_avg_score
        row['batting_team_high_innings_score'] = team_high_score
        row['batting_team_venue_high_innings_score'] = team_venue_high_score
        row['venue_avg_run_rate'] = venue_avg_rr
        row['batting_team_avg_run_rate'] = team_avg_rr
        row['batting_team_venue_avg_run_rate'] = team_venue_avg_rr
        row['batting_team_high_run_rate'] = team_high_rr
        row['batting_team_venue_high_run_rate'] = team_venue_high_rr

        if innings == 1:
            row['projected_vs_team_avg_score'] = projected_score - team_avg_score
            row['projected_vs_team_venue_avg_score'] = projected_score - team_venue_avg_score
            row['projected_vs_team_high_score'] = projected_score - team_high_score
            row['projected_vs_team_venue_high_score'] = projected_score - team_venue_high_score
        else:
            row['projected_vs_team_avg_score'] = 0.0
            row['projected_vs_team_venue_avg_score'] = 0.0
            row['projected_vs_team_high_score'] = 0.0
            row['projected_vs_team_venue_high_score'] = 0.0

        row['crr_minus_venue_avg_rr'] = current_rr - venue_avg_rr
        row['crr_minus_team_avg_rr'] = current_rr - team_avg_rr
        row['crr_minus_team_venue_avg_rr'] = current_rr - team_venue_avg_rr

        target_score_value = self._safe_float(target_score if innings == 2 else 0.0)
        target_implied_rr = (target_score_value / total_overs) if target_score_value > 0 else 0.0
        row['target_score'] = target_score_value
        row['target_implied_run_rate'] = target_implied_rr
        row['crr_minus_target_rr'] = (current_rr - target_implied_rr) if innings == 2 and target_implied_rr > 0 else 0.0
        row['target_minus_venue_avg_score'] = (target_score_value - venue_avg_score) if innings == 2 and target_score_value > 0 else 0.0
        row['target_minus_team_avg_score'] = (target_score_value - team_avg_score) if innings == 2 and target_score_value > 0 else 0.0
        row['target_minus_team_venue_avg_score'] = (target_score_value - team_venue_avg_score) if innings == 2 and target_score_value > 0 else 0.0

        phase_name = self._phase_name(row)
        self._league_indicator_updates(row, league)
        self._phase_indicator_updates(row, phase_name)
        row['phase_name'] = phase_name
        return row

    def predict(
        self,
        *,
        live_features: Dict[str, Any],
        predictor: Any,
        batting_team: str,
        bowling_team: str,
        venue: str,
        league: str | None,
        innings: int,
        over: int,
        ball: int,
        target_score: int | None,
        current_ml_prob: float | None,
        history: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if self.status != 'ready' or not self.models or not self.feature_columns:
            return {
                'status': self.status,
                'reason': 'ODM model artifacts are unavailable for live inference.',
            }

        if current_ml_prob is None:
            return {
                'status': 'unavailable',
                'reason': 'Current ML probability is not available.',
            }

        deduped_history = self._dedupe_history(history)
        if len(deduped_history) < 12:
            return {
                'status': 'warming_up',
                'history_points': len(deduped_history),
                'required_history_points': 12,
                'reason': 'ODM needs 12 distinct-ball ML probability snapshots before issuing advisory output.',
            }

        row = self._build_feature_row(
            live_features=live_features,
            predictor=predictor,
            batting_team=batting_team,
            venue=venue,
            league=league,
            innings=innings,
            over=over,
            ball=ball,
            target_score=target_score,
            current_ml_prob=current_ml_prob,
            history=deduped_history,
        )
        phase_name = row.pop('phase_name')
        X = pd.DataFrame([{column: self._safe_float(row.get(column), 0.0) for column in self.feature_columns}])

        direction_up_prob = float(self.models['direction_model'].predict_proba(X)[0, 1])
        direction_label = 'up' if direction_up_prob >= 0.5 else 'down'
        direction_confidence = max(direction_up_prob, 1.0 - direction_up_prob)

        selected_delta_mode = (self.training_manifest or {}).get('selected_delta_mode', 'raw_delta')
        momentum_baseline_12 = self._safe_float(row.get('momentum_baseline_12'), self._safe_float(row.get('ml_prob_delta_12')))
        delta_component = float(self.models['delta_model'].predict(X)[0])
        if selected_delta_mode == 'residual_delta':
            delta_point = momentum_baseline_12 + delta_component
            interval_lower = momentum_baseline_12 + float(self.models['delta_interval_lower_model'].predict(X)[0])
            interval_upper = momentum_baseline_12 + float(self.models['delta_interval_upper_model'].predict(X)[0])
        else:
            delta_point = delta_component
            interval_lower = float(self.models['delta_interval_lower_model'].predict(X)[0])
            interval_upper = float(self.models['delta_interval_upper_model'].predict(X)[0])

        adjustment = self._phase_adjustment(phase_name)
        ordered_lower = min(interval_lower, interval_upper) - adjustment
        ordered_upper = max(interval_lower, interval_upper) + adjustment

        return {
            'status': 'ready',
            'mode': 'advisory_only',
            'direction': direction_label,
            'direction_up_prob': direction_up_prob,
            'direction_confidence': direction_confidence,
            'phase': phase_name,
            'selected_delta_mode': selected_delta_mode,
            'current_ml_prob': current_ml_prob,
            'delta_12': {
                'point_estimate': delta_point,
                'point_estimate_status': 'experimental',
                'lower_90': ordered_lower,
                'upper_90': ordered_upper,
                'conformal_adjustment': adjustment,
            },
            'advisory': {
                'direction_signal': direction_label,
                'use_direction': True,
                'use_interval': True,
                'use_point_estimate': False,
                'point_estimate_note': 'Central delta estimate remains experimental and should not be treated as a primary decision signal.',
            },
            'history_points': len(deduped_history),
            'batting_team': batting_team,
            'bowling_team': bowling_team,
        }
