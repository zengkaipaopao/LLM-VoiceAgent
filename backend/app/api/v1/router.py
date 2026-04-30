"""Compatibility entrypoint for the API v1 router.

The canonical router assembly lives in ``app.api.routes`` because it wires both
public Twilio webhooks and protected application routes in one place. Keep this
module as a thin re-export so older imports do not see a stale partial route set.
"""

from app.api.routes import api_router

__all__ = ["api_router"]
