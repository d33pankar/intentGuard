"""API tests: extraction, gated scoring, read-only results."""


def _tx(body="Yes, I'm interested! Sign me up please.", **kw):
    header = {
        "product_id": "product_b",
        "product_name": "Product B",
        "date_of_call": "2026-10-17",
        "customer_name": "Test Person",
        "customer_phone": "+91 98765 43210",
        "customer_email": "test@example.com",
        "customer_address": "Patna, Bihar",
    }
    header.update(kw)
    lines = [
        f"Product ID: {header['product_id']}",
        f"Product Name: {header['product_name']}",
        f"Date of Call: {header['date_of_call']}",
        f"Customer Name: {header['customer_name']}",
        f"Customer Phone: {header['customer_phone']}",
        f"Customer Email: {header['customer_email']}",
        f"Customer Address: {header['customer_address']}",
        "---",
        body,
    ]
    return "\n".join(lines)


FIELDS = {
    "product_id": "product_b",
    "product_name": "Product B",
    "date_of_call": "2026-10-17",
    "customer_name": "Test Person",
    "customer_phone": "+91 98765 43210",
    "customer_email": "test@example.com",
    "customer_address": "Patna, Bihar",
}


def _upload(client, text, filename="call.txt", **fields):
    data = dict(FIELDS)
    data.update(fields)
    return client.post(
        "/v1/score",
        files={"file": (filename, text.encode("utf-8"), "text/plain")},
        data=data,
    )


def _extract(client, text):
    return client.post(
        "/v1/extract",
        files={"file": ("c.txt", text.encode("utf-8"), "text/plain")},
    )


def test_health(client) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_ready_reports_model(client) -> None:
    body = client.get("/ready").json()
    assert body["ready"] is True and body["model_version"]


def test_extract_finds_header_fields(client) -> None:
    body = _extract(client, _tx()).json()
    assert body["missing"] == []
    assert body["fields"]["customer_email"]["value"] == "test@example.com"
    assert body["fields"]["date_of_call"]["value"] == "2026-10-17"


def test_extract_highlights_missing(client) -> None:
    body = _extract(client, "Yes I'm interested, call me back soon.").json()
    assert set(body["missing"]) == {
        "product_id", "product_name", "date_of_call", "customer_name",
        "customer_phone", "customer_email", "customer_address",
    }


def test_extract_finds_inline_cues(client) -> None:
    text = ("Hi, my name is Ravi Kumar, call me on 9820012345 or mail "
            "ravi.k@example.com about Product B. We spoke on 2026-10-15. "
            "Yes I'm very interested, sign me up!")
    body = _extract(client, text).json()
    assert body["fields"]["customer_email"]["value"] == "ravi.k@example.com"
    assert body["fields"]["customer_phone"]["found"] is True
    assert body["fields"]["customer_name"]["value"] == "Ravi Kumar"
    assert body["fields"]["date_of_call"]["value"] == "2026-10-15"
    assert "customer_address" in body["missing"]  # honestly missed


def test_score_requires_all_fields(client) -> None:
    data = dict(FIELDS)
    del data["customer_email"]
    r = client.post(
        "/v1/score",
        files={"file": ("c.txt", _tx().encode(), "text/plain")},
        data=data,
    )
    assert r.status_code == 400
    assert "customer_email" in r.text
    assert client.get("/v1/products/product_b/results").json() == []


def test_score_rejects_product_name_mismatch(client) -> None:
    r = _upload(client, _tx(), product_name="Product A")
    assert r.status_code == 400
    assert "does not match" in r.text


def test_score_rejects_bad_and_future_dates(client) -> None:
    assert _upload(client, _tx(), date_of_call="next Friday").status_code == 400
    assert _upload(client, _tx(), date_of_call="2999-01-01").status_code == 400


def test_score_rejects_invalid_phone_email(client) -> None:
    assert _upload(client, _tx(), customer_phone="abc").status_code == 400
    assert _upload(client, _tx(), customer_email="not-an-email").status_code == 400


def test_full_flow_new_matched_and_call_date(client) -> None:
    first = _upload(client, _tx()).json()
    assert first["customer_status"] == "new"
    assert first["call_date"] == "2026-10-17"
    second = _upload(client, _tx(body="No thanks, stop calling me.")).json()
    assert second["customer_status"] == "matched"
    assert second["mid"] == first["mid"]
    rows = client.get("/v1/products/product_b/results").json()
    assert len(rows) == 1
    assert rows[0]["engine_resolution"] == "Not interested"
    assert rows[0]["call_date"] == "2026-10-17"


def test_known_mid_skips_matching(client) -> None:
    created = _upload(client, _tx()).json()
    data = dict(FIELDS, mid=created["mid"])
    r = client.post(
        "/v1/score",
        files={"file": ("c.txt", _tx().encode(), "text/plain")},
        data=data,
    )
    assert r.json()["customer_status"] == "provided"


def test_unknown_mid_rejected(client) -> None:
    assert _upload(client, _tx(), mid="MID-999999").status_code == 400


def test_conflict_returns_409_and_records_nothing(client) -> None:
    _upload(client, _tx())
    other = dict(FIELDS, customer_phone="+91 91111 11111",
                 customer_email="clash@example.com")
    _upload(client, _tx(), **{k: v for k, v in other.items()})
    before = client.get("/v1/products/product_b/results").json()
    clash = dict(FIELDS, customer_phone="+91 98765 43210",
                 customer_email="clash@example.com")
    r = client.post(
        "/v1/score",
        files={"file": ("c.txt", _tx().encode(), "text/plain")},
        data=clash,
    )
    assert r.status_code == 409
    assert "No score was recorded" in r.text
    assert client.get("/v1/products/product_b/results").json() == before


def test_products_and_404(client) -> None:
    ids = {p["product_id"] for p in client.get("/v1/products").json()}
    assert {"product_a", "product_b"} <= ids
    assert client.get("/v1/products/nope/results").status_code == 404
    assert client.get("/v1/products/nope/metrics").status_code == 404


def test_score_header_block_does_not_reach_model(client) -> None:
    body = "Yes, I'm interested! Sign me up please."
    with_header = _upload(client, _tx(body)).json()
    data = dict(FIELDS)
    data["customer_phone"] = "+91 92222 22222"
    data["customer_email"] = "second@example.com"
    body_only = client.post(
        "/v1/score",
        files={"file": ("c.txt", body.encode("utf-8"), "text/plain")},
        data=data,
    ).json()
    assert (with_header["label"], with_header["interest_score"]) == (
        body_only["label"], body_only["interest_score"])
    assert "Product ID" not in with_header["evidence"]


def test_score_header_only_transcript_rejected(client) -> None:
    header_only = "\n".join(_tx("").splitlines()[:-1])  # header + ---, no body
    r = _upload(client, header_only)
    assert r.status_code == 400
    assert "no conversation content" in r.text
    assert client.get("/v1/products/product_b/results").json() == []


def test_score_returns_structured_evidence(client) -> None:
    body = _upload(client, _tx()).json()
    assert body["evidence_verdict"]  # verdict line, not a blob
    assert body["evidence"]  # DB string still populated
    assert body["evidence_verdict"] in body["evidence"]
    assert isinstance(body["evidence_cues"], list)
    assert isinstance(body["evidence_prompt"], list)
    assert isinstance(body["evidence_excerpt"], str)


def test_score_uses_customer_scope_and_ignores_agent_hype(client) -> None:
    body = ("Agent: Excellent! Perfect! This is an absolutely amazing deal, "
            "you will love it, fantastic rewards, wonderful!\n"
            "Customer: No thanks, I am not interested. Goodbye.")
    r = _upload(client, _tx(body)).json()
    assert r["scored_scope"] == "customer"
    assert r["label"] == "DISENGAGED"  # agent hype must not inflate


def test_score_falls_back_to_whole_scope_without_labels(client) -> None:
    r = _upload(client, _tx("Just a plain block of dialogue.")).json()
    assert r["scored_scope"] == "whole"


def test_score_bare_customer_yes_abstains(client) -> None:
    body = ("Agent: Are you above 20 years of age?\n"
            "Customer: Yes.")
    r = _upload(client, _tx(body)).json()
    assert r["scored_scope"] == "customer"
    assert r["label"] == "UNCERTAIN"  # never decided on one word
    assert r["interest_score"] == 0.5
    assert r["insufficient_signal"] is True
    assert r["decision_status"] == "REQUIRES_REVIEW"


def test_score_rejects_unknown_and_misplaced_prompt_style(client) -> None:
    bad_style = client.post(
        "/v1/score",
        files={"file": ("c.txt", _tx().encode(), "text/plain")},
        data=dict(FIELDS, model="hf-zeroshot", prompt_style="pirate"),
    )
    assert bad_style.status_code == 400
    assert "Available" in bad_style.text
    misplaced = client.post(
        "/v1/score",
        files={"file": ("c.txt", _tx().encode(), "text/plain")},
        data=dict(FIELDS, model="baseline", prompt_style="direct"),
    )
    assert misplaced.status_code == 400
    assert "takes no prompt style" in misplaced.text


def test_models_advertise_prompt_styles(client) -> None:
    models = {m["name"]: m for m in client.get("/v1/models").json()}
    assert models["baseline"]["prompt_styles"] == []
    ids = [s["id"] for s in models["hf-zeroshot"]["prompt_styles"]]
    assert ids == ["direct", "literal", "role"]
