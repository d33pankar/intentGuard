"""Database engine/session. PostgreSQL is primary (star schema); SQLite is
the automatic fallback for local dev/tests when Postgres is unreachable."""
import os
from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session


class Base(DeclarativeBase):
    pass


def database_url() -> str:
    # Via pydantic-settings so a local .env file is honored (os.getenv alone
    # would ignore it). Falls back to SQLite when Postgres is not configured.
    from app.core.config import settings

    return settings.database_url or settings.sqlite_fallback_url


def _make_engine():
    url = database_url()
    kwargs: dict = {}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **kwargs)


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def _latest_view_sql(view: str, fact: str, dialect: str) -> str:
    # Portable window-function view (PostgreSQL + modern SQLite). Always
    # created fresh after a DROP, so plain CREATE VIEW suffices everywhere.
    return f"""
    CREATE VIEW {view} AS
    SELECT mid, label, interest_score, decision_status, engine_resolution,
           to_stop, evidence, model_version, call_date, scored_at
    FROM (
        SELECT f.*,
               ROW_NUMBER() OVER (PARTITION BY mid ORDER BY scored_at DESC, id DESC) AS rn
        FROM {fact} AS f
    ) ranked
    WHERE rn = 1
    """


def create_views_for(mapping: dict[str, str], target_engine=None) -> None:
    eng = target_engine or engine
    with eng.begin() as conn:
        for view, fact in mapping.items():
            conn.execute(text(f"DROP VIEW IF EXISTS {view}"))
            conn.execute(text(_latest_view_sql(view, fact, eng.dialect.name)))


def create_views(target_engine=None) -> None:
    from app.db.models import LATEST_VIEWS

    create_views_for(LATEST_VIEWS, target_engine)


def init_db() -> None:
    from app.db import models  # noqa: F401  (register tables)
    from app.db.models import fact_class_for
    from app.db.seed import seed_all

    url = database_url()
    if url.startswith("sqlite:"):
        path = url.split("sqlite:///")[-1]
        if path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    Base.metadata.create_all(engine)
    create_views()
    with SessionLocal() as session:
        seed_all(session)
        # Provision fact tables + latest views for every catalogue product,
        # including ones added directly in the database (e.g. AMEX_BB_CC).
        for (pid,) in session.query(models.DimProduct.product_id).all():
            fact_class_for(pid, engine)


def get_db() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
