from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    WEBHOOK_SECRET: str = ""
    DATABASE_URL: str = "sqlite+aiosqlite:////data/app.db"
    LOG_LEVEL: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @field_validator("DATABASE_URL")
    @classmethod
    def fix_sqlite_driver(cls, v: str) -> str:
        # If the user provided a standard sqlite url, upgrade it to async
        if v.startswith("sqlite://") and "aiosqlite" not in v:
            return v.replace("sqlite://", "sqlite+aiosqlite://")
        return v

settings = Settings()
