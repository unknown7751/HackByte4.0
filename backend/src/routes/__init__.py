from .accidents import router as accidents_router
from .volunteers import router as volunteers_router
from .tasks import router as tasks_router
from .webhooks import router as webhooks_router

__all__ = ["accidents_router", "volunteers_router", "tasks_router", "webhooks_router"]
