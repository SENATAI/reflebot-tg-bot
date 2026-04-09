from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    telegram_bot_token: SecretStr = Field(alias="TELEGRAM_BOT_TOKEN")
    reflebot_backend_base_url: str = Field(alias="REFLEBOT_BACKEND_BASE_URL")
    reflebot_api_prefix: str = Field(
        default="/api/reflections",
        alias="REFLEBOT_API_PREFIX",
    )
    reflebot_telegram_secret_token: SecretStr = Field(
        alias="REFLEBOT_TELEGRAM_SECRET_TOKEN"
    )
    rabbitmq_url: SecretStr = Field(alias="RABBITMQ_URL")
    rabbitmq_notifications_exchange: str = Field(
        default="reflebot.notifications",
        alias="RABBITMQ_NOTIFICATIONS_EXCHANGE",
    )
    rabbitmq_reflection_prompt_queue: str = Field(
        alias="RABBITMQ_REFLECTION_PROMPT_QUEUE"
    )
    rabbitmq_reflection_prompt_routing_key: str = Field(
        default="reflection_prompt.send",
        alias="RABBITMQ_REFLECTION_PROMPT_ROUTING_KEY",
    )
    rabbitmq_notification_results_exchange: str = Field(
        default="reflebot.notification-results",
        alias="RABBITMQ_NOTIFICATION_RESULTS_EXCHANGE",
    )
    rabbitmq_delivery_result_queue: str = Field(
        default="backend.notification-results",
        alias="RABBITMQ_DELIVERY_RESULT_QUEUE",
    )
    rabbitmq_delivery_result_routing_key: str = Field(
        default="reflection_prompt.result",
        alias="RABBITMQ_DELIVERY_RESULT_ROUTING_KEY",
    )
    http_timeout_seconds: float = Field(default=10.0, alias="HTTP_TIMEOUT_SECONDS")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    user_error_message: str = Field(
        default="Сервис временно недоступен. Попробуйте позже.",
        alias="USER_ERROR_MESSAGE",
    )
    username_required_message: str = Field(
        default="Укажите username в Telegram и повторите /start.",
        alias="USERNAME_REQUIRED_MESSAGE",
    )
    unsupported_attachment_message: str = Field(
        default=(
            "Поддерживаются .xlsx, .csv, документы Telegram, video и video_note."
        ),
        alias="UNSUPPORTED_ATTACHMENT_MESSAGE",
    )
    telegram_global_rate_limit_per_second: int = Field(
        default=20,
        alias="TELEGRAM_GLOBAL_RATE_LIMIT_PER_SECOND",
        ge=1,
    )
    platform_adapter: str = Field(default="telegram", alias="PLATFORM_ADAPTER")

    @property
    def telegram_token(self) -> str:
        return self.telegram_bot_token.get_secret_value()

    @property
    def service_api_key(self) -> str:
        return self.reflebot_telegram_secret_token.get_secret_value()

    @property
    def broker_url(self) -> str:
        return self.rabbitmq_url.get_secret_value()

    @property
    def backend_api_url(self) -> str:
        base = self.reflebot_backend_base_url.rstrip("/")
        prefix = self.reflebot_api_prefix
        if not prefix.startswith("/"):
            prefix = f"/{prefix}"
        return f"{base}{prefix}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
