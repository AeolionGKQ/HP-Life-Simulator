from __future__ import annotations

import os
import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "settings.local.toml"


class AppSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = "霍格沃兹人生模拟器"
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    debug: bool = False
    data_dir: str = "data"
    frontend_dist_dir: str = "frontend/dist"


class DatabaseSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str = "sqlite:///data/game.db"
    echo: bool = False


class LLMSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_url: str
    api_key: SecretStr
    model: str
    timeout_seconds: float = Field(default=90, gt=0)
    temperature: float = Field(default=0.8, ge=0, le=2)
    max_output_tokens: int = Field(default=4096, gt=0)
    supports_json_schema: bool = False
    stream: bool = False

    @field_validator("base_url")
    @classmethod
    def strip_base_url(cls, value: str) -> str:
        return value.rstrip("/")


class GameSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    era_id: str = "second_generation"
    recent_narrative_turns: int = Field(default=10, ge=1)
    recent_turn_token_limit: int = Field(default=12000, ge=1000)
    automatic_memory_recall_limit: int = Field(default=6, ge=1, le=20)
    memory_request_limit: int = Field(default=5, ge=1, le=10)
    worldline_min: float = 0.0
    worldline_max: float = 100.0

    @field_validator("worldline_max")
    @classmethod
    def validate_worldline_range(cls, value: float, info: Any) -> float:
        minimum = info.data.get("worldline_min", 0.0)
        if value <= minimum:
            raise ValueError("worldline_max 必须大于 worldline_min")
        return value


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    app: AppSettings
    database: DatabaseSettings
    llm: LLMSettings
    game: GameSettings
    project_root: Path
    config_path: Path

    @property
    def data_dir(self) -> Path:
        return _resolve_project_path(self.app.data_dir, self.project_root)

    @property
    def frontend_dist_dir(self) -> Path:
        return _resolve_project_path(self.app.frontend_dist_dir, self.project_root)

    @property
    def database_url(self) -> str:
        prefix = "sqlite:///"
        if not self.database.url.startswith(prefix):
            return self.database.url
        raw_path = self.database.url.removeprefix(prefix)
        resolved_path = _resolve_project_path(raw_path, self.project_root)
        return f"{prefix}{resolved_path.as_posix()}"


def _resolve_project_path(value: str, project_root: Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else project_root / path


def _load_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError(
            f"配置文件不存在：{path}。请复制 config/settings.example.toml "
            "为 config/settings.local.toml 并填写本地配置。"
        )
    with path.open("rb") as config_file:
        return tomllib.load(config_file)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    configured_path = os.getenv("HP_SIMULATOR_CONFIG")
    config_path = (
        Path(configured_path).expanduser().resolve()
        if configured_path
        else DEFAULT_CONFIG_PATH
    )
    raw = _load_toml(config_path)
    return Settings(
        **raw,
        project_root=PROJECT_ROOT,
        config_path=config_path,
    )

