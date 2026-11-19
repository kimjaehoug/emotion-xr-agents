"""애플리케이션 설정."""

from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "XR Control AI Agent PoC"
    debug: bool = True
    database_url: str = "sqlite:///./data/xr_agent.db"
    state_agent_database_url: Optional[str] = None
    state_agent_api_url: str = "http://127.0.0.1:8000"
    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:5174,http://127.0.0.1:5174"
    )

    local_llm_base_url: str = "http://localhost:8080/v1"
    local_llm_model: str = "qwen3.5-9b"
    local_llm_api_key: str = "local"
    local_llm_timeout_sec: int = 60
    local_llm_max_retries: int = 2
    local_llm_temperature: float = 0.1
    local_llm_max_tokens: int = 1200
    local_llm_json_schema_enabled: bool = True

    llm_repair_max_attempts: int = 1
    llm_store_sanitized_prompts: bool = False

    xr_max_parameter_delta: float = 0.20
    xr_auto_control_min_confidence: float = 0.80
    xr_observation_min_confidence: float = 0.60

    content_candidate_limit: int = 10
    content_recommendation_top_k: int = 5

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
