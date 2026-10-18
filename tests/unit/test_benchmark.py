"""Integrity tests for the frozen synthetic benchmark.

Guards the two properties every later claim depends on:
1. The manifest is a clean partition (every id exactly once, splits frozen).
2. The test split does not leak into the baseline's training corpus —
   otherwise "baseline accuracy" would measure memorisation.
"""
import json
from pathlib import Path

DS = Path(__file__).resolve().parents[2] / "datasets" / "synthetic"
LABELS = {"INTERESTED", "UNCERTAIN", "DISENGAGED"}
SCENARIOS = {"clear_interest", "explicit_rejection", "polite_deflection",
             "not_now", "contradictory", "varied_style", "opt_out", "thin_reply"}


def _records():
    return [json.loads(line) for line in
            (DS / "wts_benchmark.jsonl").read_text().splitlines() if line.strip()]


def _manifest():
    return json.loads((DS / "manifest.json").read_text())


def test_schema_labels_and_coverage() -> None:
    recs = _records()
    assert len(recs) >= 60
    ids = [r["id"] for r in recs]
    assert len(set(ids)) == len(ids)
    for r in recs:
        assert set(r) == {"id", "scenario", "expected", "text"}
        assert r["scenario"] in SCENARIOS
        assert r["expected"] in LABELS
        assert len(r["text"]) > 10
    counts: dict[str, int] = {}
    for r in recs:
        counts[r["scenario"]] = counts.get(r["scenario"], 0) + 1
    assert all(n >= 6 for n in counts.values()), counts


def test_manifest_is_clean_partition() -> None:
    m = _manifest()
    assert m["version"] == 1 and m["seed"] == 42
    splits = m["splits"]
    assert set(splits) == {"train", "val", "test"}
    assert all(len(v) >= 15 for v in splits.values())
    all_ids = [i for v in splits.values() for i in v]
    assert len(set(all_ids)) == len(all_ids)  # disjoint
    assert set(all_ids) == {r["id"] for r in _records()}  # complete


def test_no_leakage_into_baseline_training_corpus() -> None:
    from app.inference.baseline import _CLEAR_CORPUS

    train_texts = {" ".join(t.lower().split()) for t, _ in _CLEAR_CORPUS}
    test_ids = set(_manifest()["splits"]["test"])
    for r in _records():
        if r["id"] not in test_ids:
            continue
        norm = " ".join(r["text"].lower().split())
        assert norm not in train_texts, f"test item {r['id']} is a train duplicate"
        overlap = max(
            len(set(norm.split()) & set(t.split())) / len(set(norm.split()))
            for t in train_texts
        )
        assert overlap < 0.8, f"test item {r['id']} near-duplicates training"


def test_opt_out_scenarios_trigger_deterministic_rule() -> None:
    from app.inference.signals import opt_out_detected

    recs = [r for r in _records() if r["scenario"] == "opt_out"]
    assert len(recs) >= 6
    assert all(opt_out_detected(r["text"]) for r in recs)


def test_thin_replies_abstain() -> None:
    from app.inference.signals import bare_response_detected
    from app.ingestion.speakers import customer_text

    recs = [r for r in _records() if r["scenario"] == "thin_reply"]
    assert len(recs) >= 6
    scoped = [(customer_text(r["text"]) or r["text"]) for r in recs]
    assert all(bare_response_detected(t) for t in scoped)
