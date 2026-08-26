from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="IDML_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["development", "test", "staging", "production"] = "development"
    database_url: str = "sqlite+pysqlite:///./idml-development.db"
    redis_url: str = "redis://127.0.0.1:6379/0"
    artifact_root: Path = Path("./artifacts")
    session_pepper: SecretStr = SecretStr("development-only-change-this-pepper")
    mfa_encryption_key: SecretStr = SecretStr("development-only-mfa-encryption-key")
    log_level: str = "INFO"
    upload_max_bytes: int = Field(default=100 * 1024 * 1024, ge=1)
    zip_max_entries: int = Field(default=5_000, ge=1)
    zip_max_uncompressed_bytes: int = Field(default=500 * 1024 * 1024, ge=1)
    zip_max_ratio: int = Field(default=100, ge=1)
    session_ttl_seconds: int = Field(default=8 * 60 * 60, ge=300, le=7 * 24 * 60 * 60)
    feature_openclaw: bool = False
    feature_ai_swarm: bool = False
    ai_timeout_seconds: int = Field(default=45, ge=1, le=300)
    ai_max_attempts: int = Field(default=2, ge=1, le=2)
    ai_max_input_tokens: int = Field(default=12_000, ge=1)
    ai_max_output_tokens: int = Field(default=2_000, ge=1)
    ai_max_cost_microusd: int = Field(default=50_000, ge=1)
    ai_max_concurrency: int = Field(default=1, ge=1, le=1)
    ai_confidence_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    ai_max_repair_cycles: int = Field(default=2, ge=0, le=2)
    feature_clamav: bool = False
    clamav_host: str = "clamav"
    clamav_port: int = 3310

    @model_validator(mode="after")
    def reject_unsafe_production_defaults(self) -> "Settings":
        if self.environment in {"staging", "production"}:
            pepper = self.session_pepper.get_secret_value()
            if "change" in pepper.lower() or len(pepper) < 32:
                raise ValueError("IDML_SESSION_PEPPER must be a strong environment secret")
            mfa_key = self.mfa_encryption_key.get_secret_value()
            if "development" in mfa_key.lower() or len(mfa_key) < 32:
                raise ValueError("IDML_MFA_ENCRYPTION_KEY must be a strong environment secret")
            if self.database_url.startswith("sqlite"):
                raise ValueError("SQLite is not allowed outside development/test")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
