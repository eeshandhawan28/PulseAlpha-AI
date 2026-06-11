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
from api.routes.watchlist import router as watchlist_router  # noqa: E402

logger = logging.getLogger(__name__)


def _start_phoenix() -> None:
    """Launch Phoenix tracing UI (localhost:6006). No-op if not installed."""
    try:
        import phoenix as px  # noqa: PLC0415
        from openinference.instrumentation.langchain import (  # noqa: PLC0415
            LangChainInstrumentor,
        )
        from phoenix.otel import register  # noqa: PLC0415

        session = px.launch_app()
        tracer_provider = register(project_name="pulsealpha")
        LangChainInstrumentor().instrument(tracer_provider=tracer_provider)
        url = session.url if session is not None else "http://localhost:6006"
        logger.info("Phoenix trace UI → %s", url)
    except ImportError:
        logger.info(
            "Phoenix not installed — tracing disabled. "
            "Run: uv add arize-phoenix openinference-instrumentation-langchain"
        )
    except Exception as exc:
        logger.warning("Phoenix startup failed (tracing disabled): %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    s = get_settings()
    logging.basicConfig(level=getattr(logging, s.log_level))
    logger.info("PulseAlpha API starting — env=%s", s.app_env)
    _start_phoenix()
    # Accumulate today's FII/DII reading into the rolling 30-day history buffer
    import asyncio  # noqa: PLC0415

    import api.fii_dii_store as fii_dii_store  # noqa: PLC0415

    asyncio.ensure_future(fii_dii_store.append_today())
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
    app.include_router(watchlist_router)
    return app


app = create_app()
