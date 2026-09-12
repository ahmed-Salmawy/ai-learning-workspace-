from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes_ask, routes_books, routes_health
from app.core.config import get_settings
from app.core.correlation import CorrelationIdMiddleware
from app.core.logging import setup_logging


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)
    app = FastAPI(title=settings.app_name)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()
        ],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(CorrelationIdMiddleware)
    app.include_router(routes_health.router)
    app.include_router(routes_books.router)
    app.include_router(routes_ask.router)
    return app


app = create_app()
