"""IntentGuard API entrypoint (V1: manual upload + synchronous scoring)."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from app.api.routes import router
from app.core.logging import configure_logging
from app.db.database import init_db
from app.inference.baseline import MODEL_VERSION

configure_logging()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="IntentGuard",
    description="Explainable, cost-sensitive customer disengagement detection (WTS workflow).",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(router)

_UI_HTML = (Path(__file__).parent / "ui" / "index.html").read_text(encoding="utf-8")


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def ui() -> str:
    return _UI_HTML


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict:
    # V1 readiness: baseline model loads and the database answers.
    from sqlalchemy import text as sql_text

    from app.db.database import SessionLocal
    from app.inference.baseline import get_scorer

    get_scorer()
    with SessionLocal() as session:
        session.execute(sql_text("SELECT 1"))
    return {"ready": True, "model_version": MODEL_VERSION}
