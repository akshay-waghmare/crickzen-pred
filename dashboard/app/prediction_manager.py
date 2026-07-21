"""PredictionManager — manages crex_live_predictor subprocesses.

Mirrors the subprocess management logic in scripts/launcher.py MatchSlot,
but as a headless singleton suitable for the FastAPI server.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

from app.config import (
    LEAGUE_CONFIGS,
    Settings,
    detect_league_from_url,
    get_project_root,
    get_python_executable,
    get_settings,
)
from app.model_resolution import resolve_model_config

logger = logging.getLogger(__name__)

WINDOWS_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
TERMINAL_STATUSES = {"stopped", "finished", "error"}


def _normalize_match_url_key(url: str) -> str:
    """Normalize enough to detect duplicate active predictions."""
    parsed = urlparse((url or "").strip())
    path = parsed.path.rstrip("/")
    return urlunparse((parsed.scheme, parsed.netloc.lower(), path, "", "", "")).lower()


class Prediction:
    """Tracks one running crex_live_predictor subprocess."""

    def __init__(
        self,
        prediction_id: str,
        user_id: str,
        match_url: str,
        league_key: str,
        league_code: str,
        output_json_path: str,
        proc: subprocess.Popen,
    ):
        self.id = prediction_id
        self.user_id = user_id
        self.match_url = match_url
        self.league_key = league_key
        self.league_code = league_code
        self.output_json_path = output_json_path
        self.proc = proc
        self.created_at = datetime.now(timezone.utc)
        self.status = "running"
        self.status_updated_at = self.created_at

    @property
    def pid(self) -> int | None:
        return self.proc.pid if self.proc else None

    @property
    def is_alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def set_status(self, status: str) -> None:
        if self.status != status:
            self.status = status
            self.status_updated_at = datetime.now(timezone.utc)

    def refresh_status(self) -> None:
        """Synchronize status with subprocess state."""
        if self.status == "running" and not self.is_alive:
            code = self.proc.returncode if self.proc else 0
            self.set_status("finished" if code == 0 else "error")

    def latest_state_at(self) -> datetime | None:
        """Return the latest output-file write time, if any."""
        try:
            path = Path(self.output_json_path)
            if not path.exists():
                return None
            return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        except OSError:
            return None

    def is_stale_running(self, now: datetime, settings: Settings) -> bool:
        """Return true for very old running predictions that should be cleared."""
        if self.status != "running":
            return False

        cutoff = timedelta(minutes=max(1, settings.STALE_RUNNING_MATCH_MINUTES))
        newest_activity = self.latest_state_at() or self.created_at
        return now - newest_activity > cutoff

    def read_state(self) -> dict[str, Any] | None:
        """Read the latest JSON state from the output file."""
        try:
            p = Path(self.output_json_path)
            if not p.exists():
                return None
            text = p.read_text(encoding="utf-8")
            if not text.strip():
                return None
            return json.loads(text)
        except (json.JSONDecodeError, OSError) as exc:
            logger.debug("Failed to read state for %s: %s", self.id, exc)
            return None

    def state_indicates_finished(self) -> bool:
        """Return true when the latest predictor JSON shows a completed match."""
        state = self.read_state()
        if not state:
            return False
        return _state_has_result(state)

    def stop(self):
        """Kill the subprocess."""
        if self.proc and self.proc.poll() is None:
            try:
                if os.name == "nt":
                    self.proc.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
            except (OSError, ProcessLookupError):
                pass
            try:
                self.proc.kill()
            except (OSError, ProcessLookupError):
                pass
        self.set_status("stopped")


class PredictionManager:
    """Singleton that manages concurrent prediction subprocesses."""

    _instance: PredictionManager | None = None
    _lock = threading.Lock()

    def __init__(self):
        self._predictions: dict[str, Prediction] = {}
        self._monitor_threads: dict[str, threading.Thread] = {}
        self._predictions_lock = threading.RLock()

    @classmethod
    def get_instance(cls) -> PredictionManager:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def start_match(
        self,
        user_id: str,
        match_url: str,
        league_key: str | None = None,
    ) -> Prediction:
        """Start a new crex_live_predictor for the given match.

        Args:
            user_id: Authenticated user ID.
            match_url: CREX match URL.
            league_key: Optional league key (auto-detected from URL if not given).

        Returns:
            The Prediction object.

        Raises:
            ValueError: If limits exceeded or league unknown.
        """
        settings = get_settings()
        self.cleanup_expired(settings)

        # Auto-detect league
        if not league_key:
            league_key = detect_league_from_url(match_url)
        if not league_key or league_key not in LEAGUE_CONFIGS:
            raise ValueError(f"Unknown league for URL: {match_url}")

        existing = self.find_active_by_url(match_url, league_key)
        if existing is not None:
            return existing

        # Enforce the per-user limit for interactive users. The automatic
        # scheduler is a service account and must be able to cover the full
        # system capacity; applying the normal user quota to it silently
        # prevents multi-match prediction coverage.
        if user_id != "system:auto-scheduler":
            user_matches = [p for p in self._predictions.values() if p.user_id == user_id and p.is_alive]
            if len(user_matches) >= settings.MAX_USER_MATCHES:
                raise ValueError(f"You can only run {settings.MAX_USER_MATCHES} matches at a time")

        # Enforce system-wide limit
        active = [p for p in self._predictions.values() if p.is_alive]
        if len(active) >= settings.MAX_TOTAL_MATCHES:
            raise ValueError(f"System limit of {settings.MAX_TOTAL_MATCHES} concurrent matches reached")

        # Prepare paths
        cfg = resolve_model_config(league_key, LEAGUE_CONFIGS[league_key], get_project_root())
        prediction_id = uuid.uuid4().hex[:12]
        project_root = get_project_root()
        state_dir = project_root / settings.STATE_DIR
        state_dir.mkdir(parents=True, exist_ok=True)
        output_json = str(state_dir / f"{prediction_id}.json")

        # Build command (same structure as scripts/launcher.py MatchSlot.start)
        python_exe = get_python_executable()
        cmd = [
            python_exe,
            "-m", "src.bbl_pipeline.inference.crex_live_predictor",
            "--match-url", match_url,
            "--model-dir", str(project_root / cfg["model_dir"]),
            "--league", cfg["league"],
            "--output-json", output_json,
        ]
        if cfg.get("feature_store_dir"):
            cmd[cmd.index("--league"):cmd.index("--league")] = [
                "--feature-store-dir", str(project_root / cfg["feature_store_dir"])
            ]
        if cfg.get("mc_only"):
            cmd.append("--mc-only")

        logger.info("Starting prediction %s: %s → %s", prediction_id, cfg["league"], match_url[:80])

        creation_flags = WINDOWS_PROCESS_GROUP if os.name == "nt" else 0
        kwargs: dict[str, Any] = {
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "cwd": str(project_root),
        }
        if os.name == "nt":
            kwargs["creationflags"] = creation_flags
        else:
            kwargs["start_new_session"] = True

        proc = subprocess.Popen(cmd, **kwargs)

        prediction = Prediction(
            prediction_id=prediction_id,
            user_id=user_id,
            match_url=match_url,
            league_key=league_key,
            league_code=cfg["league"],
            output_json_path=output_json,
            proc=proc,
        )
        with self._predictions_lock:
            self._predictions[prediction_id] = prediction

        # Monitor thread to detect when process exits
        t = threading.Thread(target=self._watch, args=(prediction_id,), daemon=True)
        t.start()
        self._monitor_threads[prediction_id] = t

        return prediction

    def stop_match(self, prediction_id: str, user_id: str | None = None) -> bool:
        """Stop a running prediction. Returns True if stopped."""
        pred = self._predictions.get(prediction_id)
        if pred is None:
            return False
        if user_id and pred.user_id != user_id:
            return False
        pred.stop()
        return True

    def get_prediction(self, prediction_id: str) -> Prediction | None:
        pred = self._predictions.get(prediction_id)
        if pred is not None:
            pred.refresh_status()
        return pred

    def find_active_by_url(self, match_url: str, league_key: str | None = None) -> Prediction | None:
        """Return an active prediction for this CREX URL if one already exists."""
        target = _normalize_match_url_key(match_url)
        settings = get_settings()
        now = datetime.now(timezone.utc)
        for pred in self._predictions.values():
            pred.refresh_status()
            if pred.status == "running" and pred.state_indicates_finished():
                pred.set_status("finished")
                continue
            if pred.is_stale_running(now, settings):
                pred.stop()
                continue
            if not pred.is_alive:
                continue
            if league_key and pred.league_key != league_key:
                continue
            if _normalize_match_url_key(pred.match_url) == target:
                return pred
        return None

    def get_state(self, prediction_id: str) -> dict[str, Any] | None:
        pred = self._predictions.get(prediction_id)
        if pred is None:
            return None
        return pred.read_state()

    def list_predictions(self, user_id: str | None = None) -> list[dict[str, Any]]:
        """Return summary dicts for active/recent predictions."""
        self.cleanup_expired()
        results = []
        for pred in self._predictions.values():
            if user_id and pred.user_id != user_id:
                continue
            # Refresh status
            pred.refresh_status()
            results.append({
                "id": pred.id,
                "user_id": pred.user_id,
                "match_url": pred.match_url,
                "league": pred.league_key,
                "league_code": pred.league_code,
                "status": pred.status,
                "pid": pred.pid,
                "created_at": pred.created_at.isoformat(),
            })
        return results

    def cleanup_expired(self, settings: Settings | None = None) -> int:
        """Remove finished and stale predictions from the in-memory dashboard list."""
        settings = settings or get_settings()
        now = datetime.now(timezone.utc)
        finished_cutoff = timedelta(minutes=max(1, settings.FINISHED_MATCH_RETENTION_MINUTES))
        removed = 0

        with self._predictions_lock:
            for prediction_id, pred in list(self._predictions.items()):
                pred.refresh_status()
                should_remove = False

                if pred.status == "running" and pred.state_indicates_finished():
                    logger.info("Marking completed prediction %s as finished from state JSON", prediction_id)
                    if pred.is_alive:
                        pred.stop()
                    pred.set_status("finished")
                elif pred.is_stale_running(now, settings):
                    logger.info(
                        "Clearing stale running prediction %s last_activity=%s",
                        prediction_id,
                        pred.latest_state_at() or pred.created_at,
                    )
                    pred.stop()
                    should_remove = True
                elif pred.status in TERMINAL_STATUSES and now - pred.status_updated_at > finished_cutoff:
                    should_remove = True

                if should_remove:
                    self._predictions.pop(prediction_id, None)
                    self._monitor_threads.pop(prediction_id, None)
                    removed += 1

        return removed

    def cleanup_all(self):
        """Stop all running predictions (called on server shutdown)."""
        with self._predictions_lock:
            for pred in list(self._predictions.values()):
                if pred.is_alive:
                    pred.stop()
            self._predictions.clear()
            self._monitor_threads.clear()
        logger.info("All predictions cleaned up")

    # -----------------------------------------------------------------------
    # Internal
    # -----------------------------------------------------------------------

    def _watch(self, prediction_id: str):
        pred = self._predictions.get(prediction_id)
        if pred and pred.proc:
            pred.proc.wait()
            code = pred.proc.returncode
            if pred.status == "running":
                pred.set_status("finished" if code == 0 else "error")
            logger.info("Prediction %s exited (code %s)", prediction_id, code)


def _state_has_result(state: dict[str, Any]) -> bool:
    """Return true when the predictor JSON implies a match winner is already known."""
    if not isinstance(state, dict):
        return False
    if not state.get("is_second_innings"):
        return False

    score = _safe_int(state.get("score"))
    wickets = _safe_int(state.get("wickets"))
    overs = _safe_float(state.get("overs"))
    total_overs = _safe_float(state.get("total_overs"), 20.0) or 20.0
    target = _safe_int(state.get("target"))
    if target is None or score is None:
        return False

    if score >= target:
        return True
    if wickets is not None and wickets >= 10:
        return True
    if overs is not None and overs >= total_overs:
        return True
    return False


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int | None = None) -> int | None:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default
