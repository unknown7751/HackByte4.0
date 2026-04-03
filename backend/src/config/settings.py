"""
Application settings loaded from environment variables.
Uses pydantic-settings for validation and .env file support.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Database ───────────────────────────────────────────────
    DATABASE_URL: str = (
        "postgresql+asyncpg://smartaccident:smartaccident_secret"
        "@localhost:5432/smartaccident_db"
    )

    # ── App ────────────────────────────────────────────────────
    APP_ENV: str = "development"
    SECRET_KEY: str = "change_me_in_production"
    CORS_ORIGINS: str = "http://localhost:3000"

    # ── Twilio (Voice Calls) ──────────────────────────────────
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""

    # ── Google Maps ────────────────────────────────────────────
    GOOGLE_MAPS_API_KEY: str = ""

    # ── Blockchain ─────────────────────────────────────────────
    WEB3_PROVIDER_URL: str = ""
    REWARD_CONTRACT_ADDRESS: str = ""
    DEPLOYER_PRIVATE_KEY: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a list."""
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
