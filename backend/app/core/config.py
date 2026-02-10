from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "LLM Voice Agent"
    api_prefix: str = "/api/v1"
    environment: str = "local"
    # LLM & Voice settings removed (Simulation only)
    
    # Database
    database_url: str = "postgresql://dev_user:dev_password@localhost:5432/llm_voice_agent"
    
    # Debug
    debug: bool = True


settings = Settings()
