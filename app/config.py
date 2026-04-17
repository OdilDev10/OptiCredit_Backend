import os
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://prestamos_user:prestamos_pass@localhost:5432/prestamos_db"

    # Security
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7

    # Environment
    environment: Literal["development", "production"] = "development"
    app_url: str = "http://localhost:3000"

    # Email
    smtp_email: str = "noreply@prestamos.local"
    smtp_password: str = ""

    # SMS (Twilio)
    sms_enabled: bool = False
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""

    # Braintree (Payment Processing)
    braintree_merchant_id: str = ""
    braintree_public_key: str = ""
    braintree_private_key: str = ""

    # Storage
    storage_backend: Literal["local", "r2"] = "local"
    local_storage_path: str = "/app/uploads"

    # Cloudflare R2
    r2_endpoint_url: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket_name: str = ""

    # OCR
    ocr_enabled: bool = True
    ocr_required: bool = False
    ocr_device: Literal["cpu", "gpu"] = "cpu"
    ocr_use_angle_cls: bool = True
    ocr_lang: str = "es"

    # API
    api_title: str = "Kashap"
    api_version: str = "0.1.0"
    api_description: str = "Kashap SaaS para gestión de préstamos con validación OCR"

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8080"]


# Global settings instance
def _resolve_env_files() -> tuple[str, ...]:
    """Pick env files based on runtime environment and optional override."""
    explicit_env_file = os.getenv("ENV_FILE")
    if explicit_env_file:
        return (explicit_env_file,)

    environment = os.getenv("ENVIRONMENT", "development").lower()
    if environment == "production":
        return (".env.production", ".env")

    return (".env.local", ".env")


settings = Settings(_env_file=_resolve_env_files())
