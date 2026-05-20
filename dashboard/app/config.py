"""Application configuration via environment variables."""

from __future__ import annotations

import re
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Dashboard settings loaded from environment / .env file."""

    # Required
    JWT_SECRET: str = "change-me-to-a-random-secret"
    DOMAIN: str = "localhost"
    ADMIN_EMAIL: str = "admin@example.com"
    ADMIN_PASSWORD: str = "change-me"
    ADMIN_FORCE_SYNC: bool = False

    # Polling & state
    POLL_INTERVAL_MS: int = 3000
    STATE_DIR: str = "data/dashboard_states"

    # Database
    DATABASE_URL: str = "sqlite:///./auth.db"

    # Token lifetimes
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 55
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Capacity
    SESSION_CAP: int = 50
    MAX_USER_MATCHES: int = 2
    MAX_TOTAL_MATCHES: int = 6
    FINISHED_MATCH_RETENTION_MINUTES: int = 30
    STALE_RUNNING_MATCH_MINUTES: int = 30
    PUBLIC_MATCH_STALE_SECONDS: int = 300

    # Automatic match discovery/start
    AUTO_PREDICTIONS_ENABLED: bool = False
    AUTO_LEAGUE_KEY: str = "IPL"
    AUTO_MATCH_URLS: str = ""
    AUTO_DISCOVERY_URLS: str = ""
    AUTO_DISCOVER_FROM_CREX: bool = True
    AUTO_DISCOVERY_RENDER_JS: bool = True
    AUTO_DISCOVERY_INTERVAL_SECONDS: int = 300
    AUTO_START_NOT_BEFORE_LOCAL: str = "17:00"
    AUTO_START_NOT_AFTER_LOCAL: str = "23:59"
    AUTO_TIMEZONE: str = "Asia/Kolkata"

    # Registration
    REGISTRATION_OPEN: bool = True

    # Paths — resolved at startup
    PROJECT_ROOT: str = ""

    # App info
    APP_VERSION: str = "1.0.0"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


# ---------------------------------------------------------------------------
# League presets (mirrors scripts/launcher.py LEAGUE_CONFIGS)
# ---------------------------------------------------------------------------
LEAGUE_CONFIGS: dict[str, dict] = {
    "IPL": {
        "league": "ipl",
        "model_dir": "models/ipl_v17_pp_features",
        "feature_store_dir": "data/ipl_feature_store_v9",
        "series_url": "https://crex.com/series/indian-premier-league-2026-1PW",
    },
    "PSL": {
        "league": "psl",
        "model_dir": "models/t20_male_v2",
        "feature_store_dir": "data/psl_feature_store_v1",
        "series_url": "https://crex.com/series/pakistan-super-league-2026-2BK",
    },
    "BBL": {
        "league": "bbl",
        "model_dir": "models/bbl_v12",
        "feature_store_dir": "data/bbl_feature_store_v2",
    },
    "SA20": {
        "league": "sa20",
        "model_dir": "models/t20_male_v2",
        "feature_store_dir": "data/bbl_feature_store_v2",
    },
    "ILT20": {
        "league": "ilt20",
        "model_dir": "models/ilt20_v5",
        "feature_store_dir": "data/ilt_feature_store_v3",
    },
    "WPL": {
        "league": "wpl",
        "model_dir": "models/wpl_v2",
        "feature_store_dir": "data/bbl_feature_store_v2",
    },
    "T20 World Cup": {
        "league": "t20i_male",
        "model_dir": "models/t20_international_male_v2",
        "feature_store_dir": "data/t20_international_male_feature_store_v2",
    },
    "Women T20I": {
        "league": "t20i_female",
        "model_dir": "models/t20_female_v4",
        "feature_store_dir": "data/t20_female_feature_store_v4",
    },
    "SSM": {
        "league": "ssm",
        "model_dir": "models/t20_male_v2",
        "feature_store_dir": "data/bbl_feature_store_v2",
    },
    "BPL": {
        "league": "bpl",
        "model_dir": "models/t20_male_v2",
        "feature_store_dir": "data/bbl_feature_store_v2",
    },
}

# URL patterns → league key (for auto-detection)
_URL_LEAGUE_PATTERNS: list[tuple[str, str]] = [
    (r"indian-premier-league", "IPL"),
    (r"pakistan-super-league", "PSL"),
    (r"big-bash-league", "BBL"),
    (r"betway-sa20|sa20-league|sa20", "SA20"),
    (r"international-league-t20|ilt20", "ILT20"),
    (r"womens-premier-league|wpl", "WPL"),
    (r"women-tour|women-s-tour|women.*tour|ind-w|sa-w|aus-w|eng-w|nz-w|wi-w|pak-w|sl-w|ban-w", "Women T20I"),
    (r"t20-world-cup|icc-mens-t20", "T20 World Cup"),
    (r"super-smash", "SSM"),
    (r"bangladesh-premier-league|bpl", "BPL"),
]


def detect_league_from_url(url: str) -> str | None:
    """Return the LEAGUE_CONFIGS key if the URL matches a known league."""
    url_lower = url.lower()
    for pattern, league_key in _URL_LEAGUE_PATTERNS:
        if re.search(pattern, url_lower):
            return league_key
    return None


def get_project_root() -> Path:
    """Resolve the project root (repo root, two levels up from dashboard/app/)."""
    settings = get_settings()
    if settings.PROJECT_ROOT:
        return Path(settings.PROJECT_ROOT)
    return Path(__file__).resolve().parent.parent.parent


def get_python_executable() -> str:
    """Return the python executable for launching predictor subprocesses."""
    import sys
    root = get_project_root()
    candidates = [
        root / ".venv" / "Scripts" / "python.exe",
        root / ".venv" / "bin" / "python",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return sys.executable


# Singleton
_settings: Settings | None = None


def get_settings() -> Settings:
    """Return the global settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
