from pydantic import BaseModel


class ModelInfo(BaseModel):
    id: str
    name: str
    provider: str
    description: str | None = None
