from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://resumechecker:resumechecker@localhost:5432/resumechecker"
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-5"
    session_secret: str = "dev-only-insecure-secret-change-me"


settings = Settings()
