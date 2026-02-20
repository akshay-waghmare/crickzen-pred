"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Dashboard settings loaded from environment / .env file."""

    # Required
    JWT_SECRET: str = "change-me-to-a-random-secret"
    DOMAIN: str = "localhost"
    ADMIN_EMAIL: str = "admin@example.com"
    ADMIN_PASSWORD: str = "change-me"

    # Polling & state
    POLL_INTERVAL_MS: int = 3000
    STATE_FILE: str = "data/live_state.json"

    # Database
    DATABASE_URL: str = "sqlite:///./auth.db"

    # Token lifetimes
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 55
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Capacity
    SESSION_CAP: int = 50

    # Registration
    # When True: anyone can self-register at /register
    # When False: only the admin can create users via POST /auth/users
    REGISTRATION_OPEN: bool = True

    # App info
    APP_VERSION: str = "1.0.0"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


# Singleton — overridden in tests via create_app(settings_override=...)
_settings: Settings | None = None


def get_settings() -> Settings:
    """Return the global settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
