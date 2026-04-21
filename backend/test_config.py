import os
from app.core.config import settings
from app.services.twilio.official_conversational_agents import build_official_conversational_agents_config

print("Settings Agent ID:", settings.twilio_official_ca_agent_id)

try:
    config = build_official_conversational_agents_config()
    print("Success. Config is:", config)
except Exception as e:
    print("Error:", e)
