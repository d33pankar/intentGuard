"""Identity resolution tests (phone/email match, MID assignment, conflicts)."""
import pytest

from app.db.database import Base
from app.db.models import CustomerIdentifier
from app.identity.resolve import (
    IdentityConflictError,
    NoIdentifierError,
    normalize_email,
    normalize_phone,
    resolve_customer,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    S = sessionmaker(bind=engine, expire_on_commit=False)
    with S() as s:
        yield s


def test_new_customer_gets_system_mid(session) -> None:
    r = resolve_customer(
        session, phone="+91 98765 43210", email="Aarav@Example.com",
        full_name="Aarav Sharma", address="Patna",
    )
    assert r.status == "new"
    assert r.mid == "MID-000001"
    ids = {i.id_type: i.id_value for i in session.query(CustomerIdentifier).all()}
    assert ids == {"phone": "919876543210", "email": "aarav@example.com"}


def test_same_phone_matches_existing(session) -> None:
    first = resolve_customer(session, phone="9876543210", email=None)
    second = resolve_customer(session, phone="98 7654 3210", email=None)
    assert second.status == "matched" and second.mid == first.mid


def test_email_match_case_insensitive(session) -> None:
    first = resolve_customer(session, phone=None, email="Diya@Example.com")
    second = resolve_customer(session, phone=None, email="diya@example.com")
    assert second.status == "matched" and second.mid == first.mid


def test_conflicting_phone_email_flagged(session) -> None:
    a = resolve_customer(session, phone="1111111111", email=None)
    b = resolve_customer(session, phone=None, email="b@example.com")
    with pytest.raises(IdentityConflictError) as exc:
        resolve_customer(session, phone="1111111111", email="b@example.com")
    assert {exc.value.mid_phone, exc.value.mid_email} == {a.mid, b.mid}


def test_no_identifiers_rejected(session) -> None:
    with pytest.raises(NoIdentifierError):
        resolve_customer(session, phone="abc", email="not-an-email")


def test_normalization() -> None:
    assert normalize_phone("+1 (555) 123-4567") == "15551234567"
    assert normalize_phone("123") is None
    assert normalize_email("  ME@X.io ") == "me@x.io"
    assert normalize_email("nope") is None
