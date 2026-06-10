import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load .env before importing app modules so os.getenv() works for LLM config.
load_dotenv(Path(__file__).parents[3] / ".env", override=False)

from api.config import get_settings  # noqa: E402
from api.routes.analyze import router as analyze_router  # noqa: E402
from api.routes.backtest import router as backtest_router  # noqa: E402
from api.routes.health import router as health_router  # noqa: E402
from api.routes.history import router as history_router  # noqa: E402

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
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(analyze_router)
    app.include_router(backtest_router)
    app.include_router(history_router)
    return app


app = create_app()
