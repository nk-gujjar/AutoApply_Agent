from __future__ import annotations

from fastapi import FastAPI

from .a2a_routes import router as a2a_router
from .chat_routes import router as chat_router


def create_app() -> FastAPI:
    app = FastAPI(title="AutoApply Backend", version="1.0.0")
    app.include_router(chat_router)
    app.include_router(a2a_router)
    return app
