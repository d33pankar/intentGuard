"""Best-effort field extraction from free-form transcripts.

The system tries to fill the seven required scoring fields wherever they
appear in the transcript — a `Key: value` header block if present, otherwise
in-text cues ("my name is …", "+91 …", "17-10-2026", …). Every field comes
back as found (with its value) or missing. The UI highlights missing fields
for the user to complete, and scoring is gated until ALL fields are filled
(server re-validates everything — extraction is a convenience, never trust).

Documented limits: name/address extraction is pattern-based and WILL miss
unusual phrasings — that is precisely what the highlight-and-complete step
is for. Phone/email/date/product matching is deterministic.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

# Canonical field -> accepted `Key:` spellings (compared case-insensitively).
KEY_ALIASES: dict[str, tuple[str, ...]] = {
    "product_id": ("product id", "product_id", "productid"),
    "product_name": ("product name", "product_name", "productname"),
    "date_of_call": ("date of call", "date_of_call", "call date", "calldate", "date"),
    "customer_name": ("customer name", "customer_name", "name"),
    "customer_phone": ("customer phone", "customer_phone", "phone", "mobile", "contact"),
    "customer_email": ("customer email", "customer_email", "email", "e-mail"),
    "customer_address": ("customer address", "customer_address", "address"),
}

REQUIRED_FIELDS = (
    "product_id",
    "product_name",
    "date_of_call",
    "customer_name",
    "customer_phone",
    "customer_email",
    "customer_address",
)

DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d")

_MONTHS = (
    "jan", "feb", "mar", "apr", "may", "jun",
    "jul", "aug", "sep", "oct", "nov", "dec",
)
_MONTH_RE = "|".join(_MONTHS)

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"\+?\d[\d\s\-()]{5,17}\d")
_NUMERIC_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2}|\d{2}[-/]\d{2}[-/]\d{4})\b")
_TEXT_DATE_RE = re.compile(
    rf"\b(\d{{1,2}}\s+(?:{_MONTH_RE})[a-z]*\s+\d{{4}}|(?:{_MONTH_RE})[a-z]*\s+\d{{1,2}},?\s+\d{{4}})",
    re.IGNORECASE,
)
_NAME_RES = (
    re.compile(r"\bmy name is\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})"),
    re.compile(r"\bthis is\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\s+speaking\b"),
    re.compile(r"\bi am\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})"),
    re.compile(r"\bi'm\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})"),
)
_ADDRESS_RES = (
    re.compile(r"\bmy address is\s+(.+?)(?:\.|$)", re.IGNORECASE),
    re.compile(r"\bi live at\s+(.+?)(?:\.|$)", re.IGNORECASE),
    re.compile(r"\bi reside at\s+(.+?)(?:\.|$)", re.IGNORECASE),
)


@dataclass
class FieldStatus:
    value: str | None
    found: bool


def _parse_date(raw: str) -> date | None:
    raw = raw.strip().rstrip(",")
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    m = re.match(
        rf"(\d{{1,2}})\s+({_MONTH_RE})[a-z]*\s+(\d{{4}})", raw, re.IGNORECASE
    )
    if m:
        day, mon, year = int(m.group(1)), m.group(2).lower(), int(m.group(3))
        try:
            return date(year, _MONTHS.index(mon[:3]) + 1, day)
        except ValueError:
            return None
    m = re.match(
        rf"({_MONTH_RE})[a-z]*\s+(\d{{1,2}}),?\s+(\d{{4}})", raw, re.IGNORECASE
    )
    if m:
        mon, day, year = m.group(1).lower(), int(m.group(2)), int(m.group(3))
        try:
            return date(year, _MONTHS.index(mon[:3]) + 1, day)
        except ValueError:
            return None
    return None


# Full-phrase spellings only. Short aliases ("name", "phone", "email", …)
# are deliberately excluded: they exist for field *extraction*, but for
# *stripping* (destructive) they would eat dialogue lines like
# "Name: Riya here, …" or "Contact: …". A header line the stripper misses
# merely adds one metadata line to the model input; a dialogue line it
# eats can void the whole transcript.
_HEADER_KEYS = frozenset({
    "product id", "product_id",
    "product name", "product_name",
    "date of call", "date_of_call", "call date",
    "customer name", "customer_name",
    "customer phone", "customer_phone",
    "customer email", "customer_email",
    "customer address", "customer_address",
})


def strip_leading_header(text: str) -> str:
    """Drop the leading metadata block so models score conversation text only.

    Consumes lines from the top while they are blank, a ``---`` rule, or a
    ``Key: value`` line whose key is a known field alias; stops at the first
    real conversation line. Body lines are never touched.
    """
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if not stripped or stripped == "---":
            i += 1
            continue
        if ":" in stripped:
            key = " ".join(stripped.split(":")[0].strip().lower().split())
            if key in _HEADER_KEYS:
                i += 1
                continue
        break
    return "\n".join(lines[i:])


def _header_values(text: str) -> dict[str, str]:
    """Line-anchored `Key: value` pairs (the precise source when present)."""
    values: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped == "---":
            continue
        if ":" not in stripped:
            continue
        key, _, val = stripped.partition(":")
        key = " ".join(key.strip().lower().split())
        val = val.strip()
        if not val:
            continue
        for field, spellings in KEY_ALIASES.items():
            if key in spellings and field not in values:
                values[field] = val
                break
    return values


def extract_fields(
    text: str, products: list[tuple[str, str]] | None = None
) -> dict[str, FieldStatus]:
    """Extract the seven required fields. `products` is a list of
    (product_id, product_name) used for catalogue matching."""
    header = _header_values(text)
    found: dict[str, str] = dict(header)

    lowered = text.lower()
    if products:
        for pid, pname in products:
            if "product_id" not in found and re.search(
                rf"\b{re.escape(pid.lower())}\b", lowered
            ):
                found["product_id"] = pid
            if "product_name" not in found and pname.lower() in lowered:
                found["product_name"] = pname

    if "date_of_call" not in found:
        m = _NUMERIC_DATE_RE.search(text) or _TEXT_DATE_RE.search(text)
        if m:
            parsed = _parse_date(m.group(1))
            if parsed:
                found["date_of_call"] = parsed.isoformat()

    # Remove date substrings before phone hunting ("2026-10-17" holds 8 digits).
    de_dated = _NUMERIC_DATE_RE.sub(" ", text)
    de_dated = _TEXT_DATE_RE.sub(" ", de_dated)
    if "customer_email" not in found:
        m = _EMAIL_RE.search(text)
        if m:
            found["customer_email"] = m.group(0)
    if "customer_phone" not in found:
        from app.identity.resolve import normalize_phone

        for m in _PHONE_RE.finditer(de_dated):
            norm = normalize_phone(m.group(0))
            if norm:
                found["customer_phone"] = m.group(0).strip()
                break
    if "customer_name" not in found:
        for rx in _NAME_RES:
            m = rx.search(text)
            if m:
                found["customer_name"] = m.group(1).strip()
                break
    if "customer_address" not in found:
        for rx in _ADDRESS_RES:
            m = rx.search(text)
            if m and len(m.group(1).strip()) >= 4:
                found["customer_address"] = m.group(1).strip().rstrip(".")
                break

    return {
        field: FieldStatus(value=found.get(field), found=field in found)
        for field in REQUIRED_FIELDS
    }


def missing_fields(status: dict[str, FieldStatus]) -> list[str]:
    return [f for f, s in status.items() if not s.found or not (s.value or "").strip()]
