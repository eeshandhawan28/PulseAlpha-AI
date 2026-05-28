import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.config import get_settings
from api.routes.analyze import router as analyze_router
from api.routes.backtest import router as backtest_router
from api.routes.health import router as health_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    s = get_settings()
    logging.basicConfig(level=getattr(logging, s.log_level))
    logger.info("PulseAlpha API starting — env=%s", s.app_env)
    yield
    logger.info("PulseAlpha API shutdown")


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="PulseAlpha AI", version=s.version, lifespan=lifespan)
    app.include_router(health_router)
    app.include_router(analyze_router)
    app.include_router(backtest_router)
    return app


app = create_app()
