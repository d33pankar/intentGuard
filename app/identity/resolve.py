"""Deterministic customer identity resolution (spec section 7.0 rules).

Every incoming transcript carries some subset of: phone, email, name,
address. The MID is ALWAYS assigned by us — never trusted from input.

Match policy (exact, never guessed):
1. Normalize phone (digits only, >= 7 digits to count) and email
   (lowercased, basic shape check).
2. Exact phone hit -> that MID. Exact email hit -> that MID.
3. Phone and email hit DIFFERENT MIDs -> conflict: raise ConflictError so a
   human reviews it (spec: flag ambiguous secondary matches).
4. Single hit -> matched customer. Record is left untouched ("ignore for
   now") and scoring proceeds.
5. No hit -> new customer: allocate the next MID (MID-000001, ...) and store
   the observed identifiers (max 5 per type, first-seen order).

Name/address are stored as attributes on match-create; they are NOT match
keys on their own (too ambiguous without a unique key alongside).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models import CustomerIdentifier, DimCustomer, MidRegistry

MAX_IDENTIFIERS_PER_TYPE = 5
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class IdentityConflictError(Exception):
    """Phone and email point at different MIDs — needs human review."""

    def __init__(self, mid_phone: str, mid_email: str) -> None:
        super().__init__(
            f"Identifier conflict: phone belongs to {mid_phone}, "
            f"email belongs to {mid_email}. Flagged for review."
        )
        self.mid_phone = mid_phone
        self.mid_email = mid_email


class NoIdentifierError(ValueError):
    """No usable phone or email to resolve on."""


@dataclass(frozen=True)
class Resolution:
    status: str  # 'matched' | 'new'
    mid: str


def normalize_phone(raw: str | None) -> str | None:
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    # Strip a leading country-code-looking prefix only for the common
    # 12-digit '<cc:2><10-digit>' shape is overkill; keep it simple and
    # deterministic: digits as-is, minimum length 7.
    return digits if len(digits) >= 7 else None


def normalize_email(raw: str | None) -> str | None:
    if not raw:
        return None
    email = raw.strip().lower()
    return email if _EMAIL_RE.match(email) else None


def _mid_for(session: Session, id_type: str, id_value: str) -> str | None:
    row = (
        session.query(CustomerIdentifier)
        .filter_by(id_type=id_type, id_value=id_value)
        .one_or_none()
    )
    return row.mid if row else None


def _store_identifier(session: Session, mid: str, id_type: str, id_value: str) -> None:
    exists = (
        session.query(CustomerIdentifier)
        .filter_by(mid=mid, id_type=id_type, id_value=id_value)
        .one_or_none()
    )
    if exists:
        return
    count = session.query(CustomerIdentifier).filter_by(mid=mid, id_type=id_type).count()
    if count >= MAX_IDENTIFIERS_PER_TYPE:
        return  # keep the first five valid values (spec 7.0)
    session.add(CustomerIdentifier(mid=mid, id_type=id_type, id_value=id_value))


def resolve_customer(
    session: Session,
    *,
    phone: str | None,
    email: str | None,
    full_name: str = "",
    address: str = "",
) -> Resolution:
    """Resolve identifiers to a MID, creating the customer if new."""
    norm_phone = normalize_phone(phone)
    norm_email = normalize_email(email)

    mid_phone = _mid_for(session, "phone", norm_phone) if norm_phone else None
    mid_email = _mid_for(session, "email", norm_email) if norm_email else None

    if mid_phone and mid_email and mid_phone != mid_email:
        raise IdentityConflictError(mid_phone, mid_email)

    matched_mid = mid_phone or mid_email
    if matched_mid:
        return Resolution(status="matched", mid=matched_mid)

    if not norm_phone and not norm_email:
        raise NoIdentifierError(
            "Provide at least a valid phone number or email address."
        )

    # New customer: allocate the next system MID.
    registry = MidRegistry(source="transcript")
    session.add(registry)
    session.flush()  # assigns autoincrement id on Postgres and SQLite
    mid = f"MID-{registry.id:06d}"
    registry.mid = mid
    session.flush()  # persist the MID assignment BEFORE any dependent rows
    session.add(
        DimCustomer(mid=mid, full_name=(full_name or "").strip(), address=(address or "").strip())
    )
    if norm_phone:
        _store_identifier(session, mid, "phone", norm_phone)
    if norm_email:
        _store_identifier(session, mid, "email", norm_email)
    session.flush()
    return Resolution(status="new", mid=mid)
