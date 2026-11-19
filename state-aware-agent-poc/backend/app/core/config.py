"""애플리케이션 설정 (환경변수 / .env)."""

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """전역 설정. 임계값은 config로 분리하여 조정 가능하게 유지한다."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "State-Aware AI Agent PoC"
    debug: bool = True
    database_url: str = "sqlite:///./data/state_agent.db"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Baseline
    min_baseline_samples: int = 3
    use_group_default_baseline: bool = False
    baseline_trim_ratio: float = 0.1
    baseline_update_max_drift: float = 0.25

    # 상태 분류
    watch_deviation_threshold: float = 0.15
    action_deviation_threshold: float = 0.30
    persistence_threshold: int = 2
    min_confidence: float = 0.6
    min_completeness: float = 0.7
    recent_episode_window: int = 5

    # Ollama / Qwen3.5 9B — 16GB RAM 환경에서 KV 캐시 여유를 위해 ctx=4096
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3.5:9b"
    ollama_num_ctx: int = 4096
    ollama_enabled: bool = True
    ollama_timeout_sec: int = 60

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
