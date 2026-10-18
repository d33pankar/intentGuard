"""One-time migration: legacy V1 SQLite -> Postgres star schema.

Mapping (documented choice):
- customer_master rows -> mid_registry (original MID preserved) + dim_customer
  (full_name = "fname lname"). No identifiers existed pre-Milestone 4, so
  these customers match only on explicit MID until a transcript supplies
  phone/email.
- customer_product_metrics rows -> fact_product_a events. Rationale: the
  prototype only ever scored the "current transcript" channel, which is now
  Product A's historical channel; new transcripts score into Product B.
Run:  DATABASE_URL=<pg-url> PYTHONPATH=./.deps python3 scripts/migrate_sqlite_to_pg.py
Idempotent: skips MIDs / fact rows already present (matched on mid+scored_at).
"""
import os
import sqlite3
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.orm import Session  # noqa: E402

from app.db.database import SessionLocal, engine, init_db  # noqa: E402
from app.db.models import DimCustomer, FactProductA, MidRegistry  # noqa: E402

SQLITE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "intentguard.db")


def main() -> None:
    print("target:", engine.url)
    init_db()
    con = sqlite3.connect(SQLITE_PATH)
    customers = con.execute("SELECT mid, fname, lname FROM customer_master").fetchall()
    metrics = con.execute(
        "SELECT mid, label_placeholder, interest_score, decision_status,"
        " engine_resolution, to_stop, model_version, evidence, last_evaluated_at"
        " FROM (SELECT mid, interest_score, decision_status, engine_resolution,"
        " to_stop, model_version, evidence, last_evaluated_at, '' AS label_placeholder"
        " FROM customer_product_metrics)"
    ).fetchall()
    # Reconstruct labels from engine_resolution for the event rows.
    with SessionLocal() as session:
        session = session
        n_mid = n_fact = 0
        for mid, fname, lname in customers:
            if session.query(MidRegistry).filter_by(mid=mid).one_or_none() is None:
                session.add(MidRegistry(mid=mid, source="v1_sqlite"))
                session.flush()  # registry row must exist before dim_customer
                session.add(
                    DimCustomer(mid=mid, full_name=f"{fname} {lname}".strip())
                )
                n_mid += 1
        session.commit()
        for (mid, _ph, score, dstatus, resolution, to_stop, mver, evid, at) in metrics:
            label = (
                "INTERESTED" if resolution == "Interested"
                else "DISENGAGED" if resolution == "Not interested"
                else "UNCERTAIN"
            )
            exists = (
                session.query(FactProductA)
                .filter_by(mid=mid, interest_score=score)
                .one_or_none()
            )
            if exists is None:
                try:
                    scored = datetime.fromisoformat(at)
                except ValueError:
                    scored = datetime.now()
                session.add(
                    FactProductA(
                        mid=mid, label=label, interest_score=score or 0.0,
                        decision_status=dstatus or "DECIDED",
                        engine_resolution=resolution,
                        to_stop=bool(to_stop) if to_stop is not None else None,
                        evidence=evid or "", model_version=mver or "",
                        scored_at=scored,
                    )
                )
                n_fact += 1
        session.commit()
        print(f"migrated {n_mid} customers, {n_fact} product-A fact events")


if __name__ == "__main__":
    main()
