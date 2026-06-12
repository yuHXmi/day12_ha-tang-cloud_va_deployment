from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    # Server
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    environment: str = Field(default="production")
    debug: bool = Field(default=False)

    # App
    app_name: str = Field(default="Production AI Agent")
    app_version: str = Field(default="1.0.0")

    # LLM
    openai_api_key: str = Field(default="")
    llm_model: str = Field(default="gpt-4o-mini")

    # Security
    agent_api_key: str = Field(default="dev-key-change-me-in-production")
    allowed_origins: list = Field(default=["*"])

    # Rate limiting & Budget
    rate_limit_per_minute: int = Field(default=20)
    daily_budget_usd: float = Field(default=5.0)

    # Storage
    redis_url: str = Field(default="redis://localhost:6379/0")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
