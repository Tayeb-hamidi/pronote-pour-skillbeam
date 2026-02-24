"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Common service settings."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "skillbeam"
    environment: str = "development"

    database_url: str = "postgresql+psycopg2://skillbeam:skillbeam@postgres:5432/skillbeam"
    redis_url: str = "redis://redis:6379/0"

    s3_endpoint_url: str = "http://minio:9000"
    s3_public_endpoint_url: str | None = "http://localhost:9000"
    s3_access_key_id: str = "minioadmin"
    s3_secret_access_key: str = "minioadmin"
    s3_region: str = "us-east-1"
    s3_bucket: str = "skillbeam"
    s3_secure: bool = False

    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 120

    llm_provider: str = "local_vllm"
    openai_api_key: str | None = None
    local_vllm_base_url: str = "http://vllm:8000"
    mistral_api_key: str | None = None
    mistral_base_url: str = "https://api.mistral.ai/v1"
    mistral_model: str = "mistral-small-latest"
    youtube_proxy_url: str | None = None
    youtube_cookies_file: str | None = None
    enable_ocr_fallback: bool = False
    ocr_language: str = "fra+eng"
    enable_table_extraction_default: bool = True
    enable_smart_cleaning_default: bool = True

    ingest_service_url: str = "http://ingest:8000"
    generate_service_url: str = "http://generate:8000"
    export_service_url: str = "http://export:8000"

    max_upload_bytes: int = 200 * 1024 * 1024
    presigned_expiration_seconds: int = 3600
    request_timeout_seconds: int = 20
    rate_limit_per_minute: int = Field(default=120, ge=1)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings instance."""

    return Settings()
