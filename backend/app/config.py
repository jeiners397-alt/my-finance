from functools import lru_cache
from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: SecretStr
    account_tokens: dict[int, SecretStr]
    cors_origins: list[str] = ["http://localhost:5173"]
    db_pool_size: int = Field(5, ge=1, le=100)
    db_max_overflow: int = Field(5, ge=0, le=100)
    db_statement_timeout_ms: int = Field(15000, ge=1000)

    @model_validator(mode="after")
    def validate_settings(self):
        if not self.database_url.get_secret_value().startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must use postgresql+asyncpg://")
        values = [t.get_secret_value() for t in self.account_tokens.values()]
        if (
            not values
            or any(len(v) < 32 for v in values)
            or len(set(values)) != len(values)
        ):
            raise ValueError("Use unique account tokens of at least 32 characters")
        if any(k <= 0 for k in self.account_tokens):
            raise ValueError("Account IDs must be positive")
        return self


@lru_cache
def get_settings():
    return Settings()
