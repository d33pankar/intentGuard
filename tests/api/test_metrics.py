"""Metrics endpoint tests (dashboard aggregates)."""


def _upload(client, text, **data):
    fields = {
        "product_id": "product_b",
        "product_name": "Product B",
        "date_of_call": "2026-10-17",
        "customer_name": "M Tester",
        "customer_phone": data.pop("phone", "+91 90000 00001"),
        "customer_email": "m@example.com",
        "customer_address": "Test Address",
    }
    fields.update(data)
    return client.post(
        "/v1/score",
        files={"file": ("c.txt", text.encode(), "text/plain")},
        data=fields,
    )


def test_empty_product_metrics_are_zero(client) -> None:
    m = client.get("/v1/products/product_b/metrics").json()
    assert m["total_customers"] == 0
    assert m["score_buckets"] == [0, 0, 0, 0, 0]
    assert len(m["activity"]) == 14
    assert m["avg_interest_score"] is None


def test_metrics_reflect_latest_state(client) -> None:
    _upload(client, "Yes, I'm interested! Sign me up please.",
            phone="1111111111", customer_email="a1@example.com")
    _upload(client, "No thanks, not interested, stop calling me.",
            phone="2222222222", customer_email="b2@example.com")
    _upload(client, "Yes I'm interested",
            phone="1111111111", customer_email="a1@example.com")  # re-score 1st
    m = client.get("/v1/products/product_b/metrics").json()
    assert m["total_customers"] == 2
    assert m["interested"] == 1 and m["not_interested"] == 1
    assert m["needs_review"] == 0
    assert sum(m["score_buckets"]) == 2
    assert m["avg_interest_score"] is not None
    today = m["activity"][-1]
    assert sum(d["count"] for d in m["activity"]) == 3  # raw events, any day
    assert m["activity"][-1]["date"] >= m["activity"][0]["date"]  # ordered


def test_metrics_unknown_product_404(client) -> None:
    assert client.get("/v1/products/nope/metrics").status_code == 404
