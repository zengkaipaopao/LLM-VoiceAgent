from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "LLM Voice Agent"
    api_prefix: str = "/api/v1"
    environment: str = "local"
    # LLM Configuration
    google_api_key: str = ""
    default_llm_provider: str = "gemini"
    default_llm_model: str = "gemini-2.0-flash"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 2048
    llm_show_quota_notice_as_reply: bool = True

    # Twilio WebCall
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_api_key_sid: str = ""
    twilio_api_key_secret: str = ""
    twilio_twiml_app_sid: str = ""
    twilio_phone_number: str = ""
    twilio_default_identity: str = "webcall-tester"
    
    # Database
    database_url: str = "postgresql://dev_user:dev_password@localhost:5432/llm_voice_agent"
    
    # Debug
    debug: bool = True


settings = Settings()
