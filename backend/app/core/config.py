from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "LLM Voice Agent"
    api_prefix: str = "/api/v1"
    environment: str = "local"
    # LLM Configuration
    google_api_key: str = ""
    openai_api_key: str = ""
    default_llm_provider: str = "gemini"
    default_llm_model: str = "gemini-2.0-flash"
    default_live_provider: str = "gemini"
    default_live_model: str = "gemini-3.1-flash-live-preview"
    default_live_modalities: str = "AUDIO"
    default_live_voice: str = ""
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
    twilio_default_prompt_code: str = "base_appointment"
    # Comma-separated map, e.g. +815012345678:base_appointment,+815076543210:jp_cancel
    twilio_incoming_prompt_map: str = ""
    twilio_incoming_default_mode: str = "agent"
    twilio_incoming_voice_engine: str = "twilio"
    # Gemini Live turn segmentation mode for Twilio media streams:
    # - auto: Gemini automatic activity detection (recommended)
    # - manual: backend VAD + explicit ActivityEnd control (debug fallback)
    twilio_gemini_activity_mode: str = "auto"
    twilio_agent_language: str = "ja-JP"
    twilio_strict_template_provider: bool = True
    
    # Database
    database_url: str = "postgresql://dev_user:dev_password@localhost:5432/llm_voice_agent"
    redis_url: str = "redis://localhost:6379/0"
    
    # Debug
    debug: bool = False

    # Security
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    app_api_key: str = ""
    enforce_api_key_auth_in_local: bool = False
    twilio_validate_webhooks: bool = True
    twilio_webhook_tolerance_seconds: int = 300

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def api_key_auth_required(self) -> bool:
        if not (self.app_api_key or "").strip():
            return False
        return self.environment != "local" or self.enforce_api_key_auth_in_local

    @property
    def live_gateway_enabled(self) -> bool:
        return bool((self.google_api_key or "").strip())

    @property
    def twilio_webcall_enabled(self) -> bool:
        return bool(
            (self.twilio_account_sid or "").strip()
            and (self.twilio_auth_token or "").strip()
            and (self.twilio_twiml_app_sid or "").strip()
        )

    @property
    def twilio_incoming_prompt_mapping(self) -> dict[str, str]:
        mapping: dict[str, str] = {}
        raw = (self.twilio_incoming_prompt_map or "").strip()
        if not raw:
            return mapping

        for pair in raw.split(","):
            item = pair.strip()
            if not item:
                continue
            if ":" not in item:
                continue
            number, prompt_code = item.split(":", 1)
            number_key = number.strip()
            prompt_value = prompt_code.strip()
            if number_key and prompt_value:
                mapping[number_key] = prompt_value
        return mapping


settings = Settings()
