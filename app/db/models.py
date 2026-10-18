"""Star schema (Milestone 4).

Grain decisions:
- `mid_registry` is the identity spine: ONE row per real-world customer,
  holding the system-assigned canonical MID. New MIDs look like MID-000001;
  rows migrated from the V1 SQLite prototype keep their original MID.
- `dim_customer` holds slowly-changing attributes (name, address).
- `customer_identifiers` is the matching spine: normalized phone/email
  values pointing at MIDs. Matching is deterministic (exact phone, exact
  email); conflicts are flagged, never guessed.
- `fact_product_a` / `fact_product_b` are APPEND-ONLY scoring events, one
  row per scored transcript. History is never rewritten; the dashboard reads
  the latest event per MID via `v_product_{a,b}_latest`.
"""
from datetime import datetime, timezone, date as date_cls

import re

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MidRegistry(Base):
    """The MID table: canonical system-assigned customer key."""

    __tablename__ = "mid_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Assigned right after insert (MID-000001, ...); nullable only to allow
    # the insert-then-assign pattern on every backend.
    mid: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="transcript")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class DimCustomer(Base):
    """The customer table: attributes keyed by MID."""

    __tablename__ = "dim_customer"

    mid: Mapped[str] = mapped_column(
        String(32), ForeignKey("mid_registry.mid"), primary_key=True
    )
    full_name: Mapped[str] = mapped_column(String(240), default="")
    address: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class CustomerIdentifier(Base):
    """Normalized phone/email values observed per MID (match keys)."""

    __tablename__ = "customer_identifiers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mid: Mapped[str] = mapped_column(
        String(32), ForeignKey("mid_registry.mid"), index=True, nullable=False
    )
    # 'phone' | 'email' — at most the first 5 valid values of each type are
    # kept per MID, in order of first sight (spec section 7.0 rule).
    id_type: Mapped[str] = mapped_column(String(16), nullable=False)
    id_value: Mapped[str] = mapped_column(String(320), nullable=False)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("ix_identifiers_type_value", "id_type", "id_value", unique=True),
    )


class DimProduct(Base):
    __tablename__ = "dim_product"

    product_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)


class _FactBase:
    """Shared columns for per-product scoring-event fact tables."""

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mid: Mapped[str] = mapped_column(
        String(32), ForeignKey("mid_registry.mid"), index=True, nullable=False
    )
    label: Mapped[str] = mapped_column(String(16), nullable=False)
    interest_score: Mapped[float] = mapped_column(Float, nullable=False)
    decision_status: Mapped[str] = mapped_column(String(32), nullable=False)
    # Interested | Not interested | NULL (needs review). Never 'Not contacted'.
    engine_resolution: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_stop: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    evidence: Mapped[str] = mapped_column(Text, default="")
    model_version: Mapped[str] = mapped_column(String(64), default="")
    # The call's own date, taken from the mandatory transcript header.
    call_date: Mapped[date_cls | None] = mapped_column(Date, nullable=True)
    scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )


class FactProductA(Base, _FactBase):
    """Scoring events for Product A (historical channel)."""

    __tablename__ = "fact_product_a"


class FactProductB(Base, _FactBase):
    """Scoring events for Product B (current transcript channel)."""

    __tablename__ = "fact_product_b"


# Product -> fact table registry. product_a/product_b are built in; any other
# catalogue product gets its fact table + latest view auto-provisioned on
# first use (see fact_class_for). Table-per-product is the chosen design.
FACT_TABLES = {
    "product_a": FactProductA,
    "product_b": FactProductB,
}


def _slug(product_id: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", product_id.strip().lower()).strip("_")
    if not slug or not slug[0].isalpha():
        slug = f"p_{slug}"
    return slug[:48]


def fact_table_name(product_id: str) -> str:
    return f"fact_{_slug(product_id)}"


def latest_view_name(product_id: str) -> str:
    return f"v_{_slug(product_id)}_latest"


def fact_class_for(product_id: str, bind=None):
    """Return the fact model for a catalogue product, creating its table and
    latest view on first use. Idempotent and safe to call from read paths."""
    from sqlalchemy import inspect as sa_inspect

    from app.db.database import create_views_for, engine

    bind = bind if bind is not None else engine
    if product_id not in FACT_TABLES:
        FACT_TABLES[product_id] = type(
            f"Fact{_slug(product_id).title().replace('_', '')}",
            (Base, _FactBase),
            {"__tablename__": fact_table_name(product_id)},
        )
    cls = FACT_TABLES[product_id]
    existing = sa_inspect(bind)
    if not existing.has_table(cls.__tablename__):
        cls.__table__.create(bind)
    if latest_view_name(product_id) not in existing.get_view_names():
        create_views_for(
            {latest_view_name(product_id): cls.__tablename__}, target_engine=bind
        )
    return cls


LATEST_VIEWS = {
    "v_product_a_latest": "fact_product_a",
    "v_product_b_latest": "fact_product_b",
}
