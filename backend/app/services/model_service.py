

from app.repositories.model_allowlist import model_allowlist_repository
from app.services.model_registry import model_registry
from app.schemas.models import ModelInfo


class ModelService:
    def list_models(self) -> list[ModelInfo]:
        # Aggregate static + provider models; caching/provider hydration can be added here.
        return model_registry.list_models()

    def list_allowed_model_ids(self) -> list[str]:
        return model_allowlist_repository.list()

    def update_allowed_models(self, ids: list[str]) -> list[str]:
        return model_allowlist_repository.set(ids)


model_service = ModelService()
