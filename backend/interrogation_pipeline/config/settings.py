"""Process-wide settings sourced from environment / .env file.

Secrets and bootstrap-time tunables live here. Behavior tunables that the user
should be able to change at runtime (schedule cron, lookback, board IDs) live
in the SQLite `config` table and are loaded via config.runtime instead.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",
        extra="ignore",
    )

    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    tavily_api_key: str = Field(default="", alias="TAVILY_API_KEY")

    trello_api_key: str = Field(default="", alias="TRELLO_API_KEY")
    trello_token: str = Field(default="", alias="TRELLO_TOKEN")
    trello_old_board_id: str = Field(default="", alias="TRELLO_OLD_BOARD_ID")
    trello_new_board_id: str = Field(default="", alias="TRELLO_NEW_BOARD_ID")
    trello_new_list_id: str = Field(default="", alias="TRELLO_NEW_LIST_ID")

    webshare_username: str = Field(default="", alias="WEBSHARE_USERNAME")
    webshare_password: str = Field(default="", alias="WEBSHARE_PASSWORD")
    webshare_host: str = Field(default="p.webshare.io", alias="WEBSHARE_HOST")
    webshare_port: int = Field(default=80, alias="WEBSHARE_PORT")
    webshare_session_min: int = Field(default=2, alias="WEBSHARE_SESSION_MIN")
    webshare_session_max: int = Field(default=499, alias="WEBSHARE_SESSION_MAX")

    host: str = Field(default="127.0.0.1", alias="PIPELINE_HOST")
    port: int = Field(default=8765, alias="PIPELINE_PORT")
    data_dir: Path = Field(default=Path("./data"), alias="PIPELINE_DATA_DIR")
    log_level: str = Field(default="INFO", alias="PIPELINE_LOG_LEVEL")

    initial_schedule_cron: str = Field(default="0 20 * * *", alias="PIPELINE_SCHEDULE_CRON")
    initial_lookback_hours: int = Field(default=24, alias="PIPELINE_LOOKBACK_HOURS")

    @property
    def db_path(self) -> Path:
        return self.data_dir / "state.db"

    @property
    def transcripts_dir(self) -> Path:
        return self.data_dir / "transcripts"

    @property
    def cookies_dir(self) -> Path:
        return self.data_dir / "cookies"

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.transcripts_dir.mkdir(parents=True, exist_ok=True)
        self.cookies_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
