from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "LLM Voice Agent"
    api_prefix: str = "/api"
    environment: str = "local"
    openai_api_key: str | None = None
    redis_url: str = "redis://localhost:6379/0"
    telephony_provider: str = "twilio"


settings = Settings()
