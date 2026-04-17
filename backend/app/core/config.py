from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.model_defaults import DEFAULT_GENERATE_MODEL, DEFAULT_LIVE_MODEL

_BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "LLM Voice Agent"
    api_prefix: str = "/api/v1"
    environment: str = "local"
    # LLM Configuration
    google_api_key: str = ""
    google_genai_use_vertexai: bool = False
    google_cloud_project: str = ""
    google_cloud_location: str = "global"
    google_application_credentials: str = ""
    google_genai_allow_api_key_fallback: bool = True
    openai_api_key: str = ""
    default_llm_provider: str = "gemini"
    default_llm_model: str = DEFAULT_GENERATE_MODEL
    default_live_provider: str = "gemini"
    default_live_model: str = DEFAULT_LIVE_MODEL
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
    # Twilio Media Streams production path only supports Gemini automatic
    # activity detection. Any non-auto value should fail fast.
    twilio_gemini_activity_mode: str = "auto"
    # Tune Gemini Live automatic activity detection for PSTN audio and let the
    # model barge in naturally when the caller interrupts.
    twilio_gemini_activity_handling: str = "interrupt"
    twilio_gemini_turn_coverage: str = "activity_only"
    twilio_gemini_start_sensitivity: str = "high"
    twilio_gemini_end_sensitivity: str = "high"
    twilio_gemini_prefix_padding_ms: int = 120
    twilio_gemini_silence_duration_ms: int = 450
    # Batch multiple 20ms Twilio inbound frames before pushing them upstream to
    # Gemini Live to reduce websocket chatter and bridge jitter.
    twilio_media_stream_inbound_batch_ms: int = 100
    twilio_media_stream_debug_inbound_wav_enabled: bool = True
    twilio_media_stream_debug_inbound_wav_seconds: int = 5
    twilio_media_stream_debug_inbound_wav_dir: str = str(
        _BACKEND_ROOT / "recordings" / "twilio_debug_inbound"
    )
    # Runtime state backend for Twilio Media Streams / trace storage.
    # Current supported value:
    # - memory: in-process singleton stores
    twilio_runtime_store_backend: str = "memory"
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
    def google_vertex_enabled(self) -> bool:
        return bool(
            self.google_genai_use_vertexai
            and (self.google_cloud_project or "").strip()
            and (self.google_cloud_location or "").strip()
        )

    @property
    def google_genai_backend_enabled(self) -> bool:
        return self.google_vertex_enabled or bool((self.google_api_key or "").strip())

    @property
    def google_genai_backend_mode(self) -> str:
        if self.google_vertex_enabled:
            return "vertexai"
        if (self.google_api_key or "").strip():
            return "developer_api"
        return "disabled"

    @property
    def live_gateway_enabled(self) -> bool:
        return self.google_genai_backend_enabled

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
