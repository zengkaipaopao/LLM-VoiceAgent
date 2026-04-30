from app.api.routes import api_router as canonical_router
from app.api.v1.router import api_router as compatibility_router


def test_v1_router_reexports_canonical_api_router():
    assert compatibility_router is canonical_router
