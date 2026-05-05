from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg2://megaai:megaai@localhost:5432/megaai"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    max_ws_message_bytes: int = 2 * 1024 * 1024
    max_image_dimension: int = 4096
    max_frames_per_minute: int = 360
    max_preview_subscribers: int = 8

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
