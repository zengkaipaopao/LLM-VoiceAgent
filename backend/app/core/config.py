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
    twilio_official_demo_model: str = DEFAULT_LIVE_MODEL
    twilio_official_demo_voice: str = "Aoede"
    twilio_official_demo_instruction: str = (
        "あなたは日本語の電話受付AIです。"
        "自然で簡潔な音声会話を行い、ユーザーの用件を一つずつ確認してください。"
        "通話が始まったら最初に短く挨拶し、その後は相手の発話を待ってください。"
        "余計な説明、メタ発言、英語の見出しは出力しないでください。"
    )
    twilio_official_ca_agent_id: str = ""
    twilio_official_ca_deployment_id: str = ""
    twilio_official_ca_environment: str = "prod"
    twilio_official_ca_kickstart_text: str = ""
    # Comma-separated map, e.g. +815012345678:base_appointment,+815076543210:jp_cancel
    twilio_incoming_prompt_map: str = ""
    twilio_incoming_default_mode: str = "agent"
    twilio_incoming_voice_engine: str = "twilio"
    # Bridge profile for the self-built Twilio Media Streams path.
    # - cx_agent_studio: mimic the official CX Agent Studio bridge as closely as
    #   possible; keep the backend as a thin transport layer and let the
    #   upstream runtime own turn detection.
    # - legacy_manual: preserve the older locally-segmented bridge behavior.
    twilio_media_stream_bridge_profile: str = "cx_agent_studio"
    # Gemini Live activity boundary mode for the self-built Twilio Media Streams
    # bridge. This only applies when the bridge profile allows local turn
    # ownership, such as "legacy_manual".
    twilio_gemini_activity_mode: str = "auto"
    # Keep Gemini Live automatic activity detection close to the native-audio
    # defaults first, then tune from production traces only when needed.
    twilio_gemini_activity_handling: str = "interrupt"
    twilio_gemini_turn_coverage: str = "activity_only"
    twilio_gemini_start_sensitivity: str = "low"
    twilio_gemini_end_sensitivity: str = "low"
    twilio_gemini_prefix_padding_ms: int = 100
    twilio_gemini_silence_duration_ms: int = 800
    twilio_greeting_interrupt_guard_ms: int = 900
    # Batch multiple 20ms Twilio inbound frames before pushing them upstream to
    # Gemini Live to reduce websocket chatter and bridge jitter.
    twilio_media_stream_inbound_batch_ms: int = 20
    # Input conditioning before forwarding Twilio inbound audio to Gemini Live.
    # This is not local turn detection; it only suppresses low-energy noise tails
    # that otherwise keep Gemini automatic activity detection from closing a turn.
    twilio_media_stream_input_noise_gate_enabled: bool = True
    twilio_media_stream_input_noise_gate_open_rms: int = 140
    twilio_media_stream_input_noise_gate_close_rms: int = 90
    twilio_media_stream_input_noise_gate_hold_ms: int = 240
    twilio_media_stream_playback_clear_rms: int = 120
    twilio_media_stream_playback_clear_min_hits: int = 3
    twilio_media_stream_playback_overlap_buffer_ms: int = 800
    twilio_media_stream_upstream_activity_rms: int = 48
    twilio_media_stream_pause_flush_seconds: float = 1.0
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
    def twilio_official_ca_configured(self) -> bool:
        return bool(
            (self.twilio_official_ca_agent_id or "").strip()
            or (self.twilio_official_ca_deployment_id or "").strip()
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
