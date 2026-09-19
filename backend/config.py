from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    spotify_client_id: str
    spotify_client_secret: str
    spotify_redirect_uri: str = "https://spotify-ai-classifier-production.up.railway.app/auth/callback"

    gemini_api_key: str
    gemini_model: str = "gemini-3.1-flash-lite"

    database_url: str = "sqlite:///./spotify_ai.db"

    session_secret: str

    poll_interval_seconds: int = 300
    playlist_public: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()