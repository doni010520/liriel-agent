from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    app_env: str = "production"
    app_port: int = 8000
    log_level: str = "INFO"

    # Database
    database_url: str = "postgresql+asyncpg://liriel:liriel_secret@postgres:5432/liriel_db"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    openai_temperature: float = 0.3
    openai_max_tokens: int = 1024

    # Uazapi
    uazapi_base_url: str = ""
    uazapi_api_key: str = ""  # Instance token (header: token)

    # Buffer
    buffer_delay_seconds: int = 12
    max_history_messages: int = 20

    # Webhook
    webhook_secret: str = ""

    # Admin
    # Comma-separated phone numbers (digits only, e.g. "557193061031,557188888888")
    # whose Contact row should be auto-flagged is_admin=True at boot.
    admin_phones: str = "557193061031"

    # WhatsApp profile name (max 25 chars, pushed to Uazapi /profile/name on boot
    # when it differs from the current account name).
    profile_name: str = "Lírio Armação"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def admin_phone_list(self) -> list[str]:
        return [p.strip() for p in self.admin_phones.split(",") if p.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
