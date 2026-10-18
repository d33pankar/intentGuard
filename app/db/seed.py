"""Seed catalogue data (synthetic, spec section 14)."""
from sqlalchemy.orm import Session

from app.db.models import DimProduct

PRODUCTS = [
    ("product_a", "Product A"),
    ("product_b", "Product B"),
]


def seed_all(session: Session) -> None:
    for product_id, product_name in PRODUCTS:
        if session.get(DimProduct, product_id) is None:
            session.add(DimProduct(product_id=product_id, product_name=product_name))
    session.commit()
