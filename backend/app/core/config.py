from functools import lru_cache
from typing import Any

from pydantic import Field, SecretStr, SerializerFunctionWrapHandler, model_serializer
from pydantic_settings import BaseSettings, SettingsConfigDict


_SECRET_FIELDS = (
    "jwt_secret",
    "supabase_jwt_secret",
    "llm_api_key",
    "qdrant_api_key",
    "langchain_api_key",
)
_URL_FIELDS = ("database_url", "redis_url", "qdrant_url")


def _redact_url_password(value: str) -> str:
    scheme_end = value.find("://")
    if scheme_end < 0:
        return value

    authority_start = scheme_end + 3
    authority_end = len(value)
    for delimiter in "/?#":
        position = value.find(delimiter, authority_start)
        if position >= 0:
            authority_end = min(authority_end, position)

    authority = value[authority_start:authority_end]
    user_info, separator, host = authority.rpartition("@")
    if not separator or ":" not in user_info:
        return value

    username, _, _ = user_info.partition(":")
    return (
        value[:authority_start]
        + username
        + ":**********@"
        + host
        + value[authority_end:]
    )


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    demo_mode: bool = True
    environment: str = "development"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    jwt_secret: SecretStr = SecretStr("")
    supabase_jwt_secret: SecretStr = SecretStr("")

    database_url: str = "sqlite+aiosqlite:///./data/support.db"
    checkpoint_db_path: str = "./data/checkpoints.db"
    redis_url: str = ""
    use_fake_redis: bool = False

    llm_provider: str = "fake"
    llm_api_key: SecretStr = SecretStr("")
    llm_model: str = ""

    embedding_provider: str = "fake"
    embedding_model: str = ""
    embedding_dimensions: int = Field(default=384, gt=0)

    vector_store: str = "memory"
    qdrant_url: str = ""
    qdrant_api_key: SecretStr = SecretStr("")
    qdrant_collection: str = "clouddesk_knowledge"

    approval_required_for_refunds: bool = True
    max_refund_without_approval: int = Field(default=0, ge=0)
    tool_timeout_seconds: float = Field(default=30.0, gt=0)
    rate_limit_per_minute: int = Field(default=120, gt=0)
    sample_data_dir: str = "sample_data"

    langchain_tracing_v2: bool = False
    langchain_api_key: SecretStr = SecretStr("")
    langchain_project: str = "clouddesk-support"

    @property
    def effective_jwt_secret(self) -> str:
        supabase_secret = self.supabase_jwt_secret.get_secret_value()
        return supabase_secret or self.jwt_secret.get_secret_value()

    @model_serializer(mode="wrap")
    def _redact_sensitive_values(
        self, handler: SerializerFunctionWrapHandler
    ) -> dict[str, Any]:
        values = handler(self)
        for field in _SECRET_FIELDS:
            if field in values and values[field] is not None:
                values[field] = "**********"
        for field in _URL_FIELDS:
            value = values.get(field)
            if isinstance(value, str):
                values[field] = _redact_url_password(value)
        return values


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
