"""Field extraction unit tests (deterministic, no DB needed)."""
from app.ingestion.extract import extract_fields, missing_fields, strip_leading_header

PRODUCTS = [("product_a", "Product A"), ("product_b", "Product B")]

HEADER_TX = """Product ID: product_b
Product Name: Product B
Date of Call: 2026-10-17
Customer Name: Aarav Sharma
Customer Phone: +91 98765 43210
Customer Email: aarav@example.com
Customer Address: 12 MG Road, Patna
---
Yes, I'm interested! Please sign me up today."""


def test_header_block_fully_extracted() -> None:
    s = extract_fields(HEADER_TX, PRODUCTS)
    assert missing_fields(s) == []
    assert s["product_id"].value == "product_b"
    assert s["date_of_call"].value == "2026-10-17"
    assert s["customer_phone"].value == "+91 98765 43210"


def test_bare_transcript_reports_all_missing() -> None:
    s = extract_fields("Yes, this sounds good, tell me more.", PRODUCTS)
    assert set(missing_fields(s)) == {
        "product_id", "product_name", "date_of_call", "customer_name",
        "customer_phone", "customer_email", "customer_address",
    }


def test_date_not_mistaken_for_phone() -> None:
    s = extract_fields("We spoke on 2026-10-17. Yes I'm interested.", PRODUCTS)
    assert s["date_of_call"].value == "2026-10-17"
    assert "customer_phone" in missing_fields(s)  # date digits must not match


def test_inline_cues_found() -> None:
    text = ("Hello, my name is Diya Patel. Reach me at 98111 22233 or "
            "diya.p@mail.com regarding your credit card. I live at 44 Park "
            "Street, Kolkata. I spoke to you on 15/10/2026. I am interested!")
    s = extract_fields(text, PRODUCTS)
    assert s["customer_name"].value == "Diya Patel"
    assert s["customer_email"].value == "diya.p@mail.com"
    assert s["customer_phone"].found is True
    assert s["customer_address"].value == "44 Park Street, Kolkata"
    assert s["date_of_call"].value == "2026-10-15"


def test_strip_leading_header_keeps_body_only() -> None:
    body = strip_leading_header(HEADER_TX)
    assert body.strip() == "Yes, I'm interested! Please sign me up today."
    assert "Product ID" not in body


def test_strip_leading_header_never_eats_conversation() -> None:
    text = "Agent: hello!\nCaller: Date: tomorrow works for me."
    assert strip_leading_header(text) == text  # stops at first non-header line
    assert strip_leading_header("Just a plain transcript.") == "Just a plain transcript."


def test_strip_keeps_short_label_dialogue_lines() -> None:
    # "Name:" / "Contact:" etc. are extraction aliases, but must never be
    # treated as header lines — they routinely start real dialogue.
    text = "Name: Riya here, thanks for calling.\nContact: me tomorrow after 5pm."
    assert strip_leading_header(text) == text
