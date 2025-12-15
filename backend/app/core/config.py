from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "LLM Voice Agent"
    api_prefix: str = "/api"
    environment: str = "local"
    openai_api_key: str | None = None
    openai_models: str | None = None  # comma-separated model ids
    openai_realtime_model: str = "gpt-4o-realtime-preview-2024-12-17"
    openai_realtime_voice: str = "alloy"
    openai_realtime_instructions: str = "你是 LLM Voice Agent 的实时调试助手，请使用简洁、专业且自然的中文语气回应用户。"
    gemini_api_key: str | None = None
    gemini_models: str | None = None  # comma-separated model ids
    gemini_model: str | None = None  # fallback for single model env var
    claude_api_key: str | None = None
    claude_models: str | None = None  # comma-separated model ids
    redis_url: str = "redis://localhost:6379/0"
    telephony_provider: str = "twilio"
    google_tts_access_token: str | None = None
    google_tts_credentials_path: str | None = None
    infobip_base_url: str | None = None
    infobip_api_key: str | None = None
    infobip_voice_from: str | None = None
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_phone_number: str | None = None
    twilio_twiml_app_sid: str | None = None
    twilio_api_key_sid: str | None = None
    twilio_api_key_secret: str | None = None
    twilio_prompt_id: str | None = None
    twilio_say_voice: str | None = None
    twilio_say_language: str | None = None
    twilio_chat_model_id: str | None = None


settings = Settings()
