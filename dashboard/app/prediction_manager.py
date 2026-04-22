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
from datetime import datetime, timezone
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

logger = logging.getLogger(__name__)

WINDOWS_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)


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

    @property
    def pid(self) -> int | None:
        return self.proc.pid if self.proc else None

    @property
    def is_alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

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
        self.status = "stopped"


class PredictionManager:
    """Singleton that manages concurrent prediction subprocesses."""

    _instance: PredictionManager | None = None
    _lock = threading.Lock()

    def __init__(self):
        self._predictions: dict[str, Prediction] = {}
        self._monitor_threads: dict[str, threading.Thread] = {}

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

        # Auto-detect league
        if not league_key:
            league_key = detect_league_from_url(match_url)
        if not league_key or league_key not in LEAGUE_CONFIGS:
            raise ValueError(f"Unknown league for URL: {match_url}")

        existing = self.find_active_by_url(match_url, league_key)
        if existing is not None:
            return existing

        # Enforce per-user limit
        user_matches = [p for p in self._predictions.values() if p.user_id == user_id and p.is_alive]
        if len(user_matches) >= settings.MAX_USER_MATCHES:
            raise ValueError(f"You can only run {settings.MAX_USER_MATCHES} matches at a time")

        # Enforce system-wide limit
        active = [p for p in self._predictions.values() if p.is_alive]
        if len(active) >= settings.MAX_TOTAL_MATCHES:
            raise ValueError(f"System limit of {settings.MAX_TOTAL_MATCHES} concurrent matches reached")

        # Prepare paths
        cfg = LEAGUE_CONFIGS[league_key]
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
            "--feature-store-dir", str(project_root / cfg["feature_store_dir"]),
            "--league", cfg["league"],
            "--output-json", output_json,
        ]

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
        return self._predictions.get(prediction_id)

    def find_active_by_url(self, match_url: str, league_key: str | None = None) -> Prediction | None:
        """Return an active prediction for this CREX URL if one already exists."""
        target = _normalize_match_url_key(match_url)
        for pred in self._predictions.values():
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
        results = []
        for pred in self._predictions.values():
            if user_id and pred.user_id != user_id:
                continue
            # Refresh status
            if pred.status == "running" and not pred.is_alive:
                pred.status = "finished"
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

    def cleanup_all(self):
        """Stop all running predictions (called on server shutdown)."""
        for pred in list(self._predictions.values()):
            if pred.is_alive:
                pred.stop()
        self._predictions.clear()
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
                pred.status = "finished" if code == 0 else "error"
            logger.info("Prediction %s exited (code %s)", prediction_id, code)
