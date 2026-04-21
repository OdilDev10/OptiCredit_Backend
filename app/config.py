import os
import json
from typing import Literal

from pydantic import field_validator
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    # Database
    database_url: str = (
        "postgresql+asyncpg://prestamos_user:prestamos_pass@localhost:5432/prestamos_db"
    )

    # Security
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7

    # Environment
    environment: Literal["development", "production"] = "development"
    app_url: str = "http://localhost:3000"
    enable_startup_seed: bool = False

    # Email (Resend)
    mail_resend_api_key: str = ""
    mail_from_email: str = "OptiCredit <noreply@opticredit.app>"
    mail_from_name: str = "OptiCredit"
    support_inbox_email: str = "support@opticredit.app"

    # Legacy SMTP (deprecated - use Resend)
    smtp_email: str = ""
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
    storage_backend: Literal["local", "r2"] = "r2"
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
    api_title: str = "OptiCredit"
    api_version: str = "0.1.0"
    api_description: str = "OptiCredit SaaS para gestión de préstamos con validación OCR"

    # CORS
    cors_origins: list[str] = [
        "http://localhost:4321",
        "http://127.0.0.1:4321",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value):
        """Accept JSON array or comma-separated CORS origins from env vars."""
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []
            if raw.startswith("["):
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, list):
                        return parsed
                except json.JSONDecodeError:
                    pass
            return [item.strip() for item in raw.split(",") if item.strip()]
        return value

    @field_validator("storage_backend", mode="before")
    @classmethod
    def _force_r2_backend(cls, value):
        """Always force R2 backend even if env accidentally sets local."""
        if isinstance(value, str) and value.strip().lower() == "local":
            return "r2"
        return value

    @model_validator(mode="after")
    def _validate_storage_backend(self):
        """Force R2-ready configuration when storage backend is enabled as r2."""
        missing = []
        if not self.r2_endpoint_url.strip():
            missing.append("R2_ENDPOINT_URL")
        if not self.r2_access_key_id.strip():
            missing.append("R2_ACCESS_KEY_ID")
        if not self.r2_secret_access_key.strip():
            missing.append("R2_SECRET_ACCESS_KEY")
        if not self.r2_bucket_name.strip():
            missing.append("R2_BUCKET_NAME")

        if missing:
            missing_envs = ", ".join(missing)
            raise ValueError(f"Missing required R2 env vars: {missing_envs}")

        return self


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
