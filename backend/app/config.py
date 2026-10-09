from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: Literal["ollama", "anthropic"] = "ollama"
    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_model: str = "qwen3:4b-instruct-2507-q4_K_M"
    ollama_num_ctx: int = 8192
    embed_model: str = "nomic-embed-text"
    anthropic_api_key: SecretStr = SecretStr("")
    anthropic_model: str = "claude-sonnet-4-6"
    llm_max_tokens: int = 3000
    llm_timeout_s: int = 120
    retrieval_top_k: int = 5
    retrieval_min_score: float = 0.69
    database_url: str = "postgresql://lenny:lenny@db:5432/lenny"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
