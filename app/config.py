from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import ClassVar

class Settings(BaseSettings):
    # 1. The Secret Key (Required)
    WEBHOOK_SECRET: str = ""

    # 2. Database Connection
    DATABASE_URL: str = "sqlite+aiosqlite:////data/app.db"

    # 3. Logging Level
    LOG_LEVEL: str = "INFO"

    model_config: ClassVar[SettingsConfigDict]= SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
