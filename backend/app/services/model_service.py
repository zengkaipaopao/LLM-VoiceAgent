from app.repositories.models import model_repository
from app.schemas.models import ModelInfo


class ModelService:
    def list_models(self) -> list[ModelInfo]:
        # Pass-through to repository; layer kept for future caching/provider hydration.
        return model_repository.list()


model_service = ModelService()
