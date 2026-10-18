"""Dynamic fact-table provisioning for catalogue products without one
(e.g. AMEX_BB_CC, which was added directly in the database)."""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import create_views
from app.db.models import (
    Base,
    DimProduct,
    fact_class_for,
    fact_table_name,
    latest_view_name,
)


def test_new_catalogue_product_gets_table_and_view() -> None:
    e = create_engine("sqlite://", connect_args={"check_same_thread": False},
                      poolclass=StaticPool)
    Base.metadata.create_all(e)
    create_views(e)
    S = sessionmaker(bind=e, expire_on_commit=False)
    with S() as s:
        s.add(DimProduct(product_id="AMEX_BB_CC", product_name="amex_biz_plat"))
        s.commit()
        cls = fact_class_for("AMEX_BB_CC", e)
        assert cls.__tablename__ == "fact_amex_bb_cc" == fact_table_name("AMEX_BB_CC")
        assert fact_class_for("AMEX_BB_CC", e) is cls  # cached, no-op
        assert latest_view_name("AMEX_BB_CC") == "v_amex_bb_cc_latest"
        assert s.execute(text("SELECT * FROM v_amex_bb_cc_latest")).fetchall() == []
