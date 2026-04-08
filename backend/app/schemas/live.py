from pydantic import BaseModel, Field


class LiveAuthTokenRequest(BaseModel):
    model: str | None = Field(default=None, description="Optional live model override.")
    modalities: list[str] | None = Field(default=None, description="Requested response modalities.")
    voice: str | None = Field(default=None, description="Optional voice override.")
    template_code: str | None = Field(default=None, description="Prompt template code.")
    system_instruction: str | None = Field(default=None, description="Optional raw system instruction.")


class LiveAuthTokenResponse(BaseModel):
    auth_token: str = Field(..., description="Ephemeral auth token resource name.")
    model: str = Field(..., description="Resolved Gemini Live model.")
    modalities: list[str] = Field(..., description="Effective response modalities.")
    voice: str | None = Field(default=None, description="Effective voice name.")
    template_code: str | None = Field(default=None, description="Resolved prompt template code.")
    system_instruction: str | None = Field(default=None, description="Resolved system instruction.")
    display_endpoint: str = Field(..., description="User-facing description of the client-to-server route.")
