from pydantic import BaseModel, Field


class TwilioTokenResponse(BaseModel):
    token: str = Field(..., description="Twilio Voice SDK access token")
    identity: str = Field(..., description="Client identity encoded in token")
    expires_in: int = Field(..., description="Seconds until token expiration")
    twiml_app_sid: str = Field(..., description="Associated TwiML App SID")
