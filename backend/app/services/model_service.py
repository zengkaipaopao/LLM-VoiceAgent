from app.services.model_registry import model_registry
from app.schemas.models import ModelInfo


class ModelService:
    def list_models(self) -> list[ModelInfo]:
        # Aggregate static + provider models; caching/provider hydration can be added here.
        return model_registry.list_models()


model_service = ModelService()
