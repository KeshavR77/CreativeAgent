"""FastAPI application entrypoint.

Exposes ``app`` and ``GET /api/health``. The lifespan builds the durable
stores + the LangGraph checkpointer and a
``RunManager``, stashing them on ``app.state`` for the project/SSE routers.

Everything still boots with ZERO provider keys: storage is local SQLite, the
checkpointer is a file DB, and every model call resolves to the mock.
"""

from __future__ import annotations

import logging
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from starlette.requests import Request

from app.config import DATA_DIR, GENERATED_DIR, get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Emit one INFO line per provider row on startup.
    get_settings().log_providers()

    # Durable stores (registry + event log + in-process pub/sub).
    from app.storage.db import init_db, make_engine, make_sessionmaker
    from app.storage.repo import EventBus, EventRepo, RegistryRepo

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    engine = make_engine(f"sqlite:///{DATA_DIR / 'app.sqlite'}")
    init_db(engine)
    session_factory = make_sessionmaker(engine)
    registry = RegistryRepo(session_factory)
    bus = EventBus()
    events = EventRepo(session_factory, bus)

    # LangGraph checkpointer — a long-lived AsyncSqliteSaver kept open for the
    # whole app lifetime via an AsyncExitStack.
    from app.graph.runner import RunManager
    from app.storage.checkpoint import open_checkpointer

    async with AsyncExitStack() as stack:
        saver = await stack.enter_async_context(
            open_checkpointer(str(DATA_DIR / "graph.sqlite"))
        )
        run_manager = RunManager(registry, events, bus, saver)

        app.state.engine = engine
        app.state.registry = registry
        app.state.events = events
        app.state.bus = bus
        app.state.run_manager = run_manager
        app.state.pending_briefs = {}
        app.state.pending_modes = {}  # project_id -> ideation_mode chosen at create

        # Boot recovery: re-drive any run left mid-flight by a previous
        # process from its last checkpoint. No-op on a clean start.
        await run_manager.resume_all()

        yield


app = FastAPI(
    title="AI Creative Agency Platform — backend",
    version="0.1.0",
    lifespan=lifespan,
)


@app.exception_handler(HTTPException)
async def _http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    """Render HTTPExceptions as the {"error": {code, message}} envelope."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.status_code, "message": exc.detail}},
    )


@app.get("/api/health")
def health() -> dict:
    """Return the resolved provider health snapshot."""
    return get_settings().health_snapshot()


# Routers are imported here (not at lifespan) so route registration happens at
# import time; their handlers read dependencies off app.state at request time.
from app.api.routes_directions import router as directions_router  # noqa: E402
from app.api.routes_events import router as events_router  # noqa: E402
from app.api.routes_export import router as export_router  # noqa: E402
from app.api.routes_projects import router as projects_router  # noqa: E402

app.include_router(projects_router)
app.include_router(directions_router)
app.include_router(export_router)
app.include_router(events_router)

# Serve generated/placeholder images; path matches ImageRef.url ("/generated/...").
from fastapi.staticfiles import StaticFiles  # noqa: E402

GENERATED_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/generated", StaticFiles(directory=str(GENERATED_DIR)), name="generated")
