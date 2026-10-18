"""Frozen-benchmark evaluation for IntentGuard scorers.

Scores the manifest split exactly as the API would (customer-scoped text,
deterministic guards inside the scorers) and reports accuracy, macro F1,
confusion matrix, false-stop / false-continue counts, review rate, and a
per-scenario table with a polite-deflection row.

The TEST split is frozen: never tune prompts, weights, or thresholds
against it. Tune on val, report on test.

Usage:
    PYTHONPATH=./.deps python3 scripts/eval_benchmark.py [--split test]
        [--models baseline,hf-zeroshot] [--styles direct,literal,role]
        [--save]
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".deps"))
sys.path.insert(0, str(ROOT))

LABELS = ["INTERESTED", "UNCERTAIN", "DISENGAGED"]


def load_split(split: str) -> list[dict]:
    ds = ROOT / "datasets" / "synthetic"
    recs = [json.loads(line) for line in
            (ds / "wts_benchmark.jsonl").read_text().splitlines() if line.strip()]
    manifest = json.loads((ds / "manifest.json").read_text())
    want = set(manifest["splits"][split])
    return [r for r in recs if r["id"] in want]


def evaluate(model: str, style: str, records: list[dict]) -> dict:
    from app.ingestion.speakers import customer_text
    from app.inference.registry import get_scorer_by_name

    scorer = get_scorer_by_name(model, style)
    rows = []
    for r in records:
        scoped = customer_text(r["text"]) or r["text"]
        pred = scorer.score(scoped)
        rows.append({
            "id": r["id"], "scenario": r["scenario"],
            "expected": r["expected"], "predicted": pred.label,
            "score": round(pred.interest_score, 3),
        })
    return {"model": model, "style": style,
            "model_version": scorer.model_version, "rows": rows}


def metrics(rows: list[dict]) -> dict:
    from sklearn.metrics import confusion_matrix, f1_score

    y_true = [r["expected"] for r in rows]
    y_pred = [r["predicted"] for r in rows]
    correct = sum(t == p for t, p in zip(y_true, y_pred))
    by_scen: dict[str, dict[str, int]] = {}
    for r in rows:
        s = by_scen.setdefault(r["scenario"], {"n": 0, "ok": 0})
        s["n"] += 1
        s["ok"] += r["expected"] == r["predicted"]
    return {
        "n": len(rows),
        "accuracy": round(correct / len(rows), 3),
        "macro_f1": round(float(f1_score(y_true, y_pred, labels=LABELS,
                                         average="macro", zero_division=0)), 3),
        "confusion_matrix": {
            "labels": LABELS,
            "rows_true_cols_pred": confusion_matrix(
                y_true, y_pred, labels=LABELS).tolist(),
        },
        "false_stop": sum(1 for r in rows if r["expected"] == "INTERESTED"
                          and r["predicted"] == "DISENGAGED"),
        "false_continue": sum(1 for r in rows if r["expected"] == "DISENGAGED"
                              and r["predicted"] == "INTERESTED"),
        "review_rate": round(sum(1 for r in rows
                                if r["predicted"] == "UNCERTAIN") / len(rows), 3),
        "by_scenario": {k: round(v["ok"] / v["n"], 3)
                        for k, v in sorted(by_scen.items())},
        "errors": [f"{r['id']} [{r['scenario']}] exp={r['expected']} "
                   f"got={r['predicted']} ({r['score']})" for r in rows
                   if r["expected"] != r["predicted"]],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test", choices=["train", "val", "test"])
    ap.add_argument("--models", default="baseline,hf-zeroshot")
    ap.add_argument("--styles", default="direct",
                    help="comma list; HF only (baseline ignores styles)")
    ap.add_argument("--save", action="store_true",
                    help="write JSON report to artifacts/eval/")
    args = ap.parse_args()

    records = load_split(args.split)
    print(f"split={args.split} n={len(records)} "
          f"(frozen manifest v{json.loads((ROOT / 'datasets' / 'synthetic' / 'manifest.json').read_text())['version']})")
    report = {"split": args.split, "results": []}
    for model in [m.strip() for m in args.models.split(",") if m.strip()]:
        styles = ([s.strip() for s in args.styles.split(",") if s.strip()]
                  if model == "hf-zeroshot" else [""])
        for style in styles:
            try:
                res = evaluate(model, style, records)
            except RuntimeError as exc:
                print(f"- {model}/{style or '-'}: SKIPPED ({exc})")
                continue
            m = metrics(res["rows"])
            tag = f"{model}/{style}" if style else model
            print(f"\n== {tag} ({res['model_version']}) ==")
            print(f"acc={m['accuracy']} macroF1={m['macro_f1']} "
                  f"false_stop={m['false_stop']} false_continue={m['false_continue']} "
                  f"review={m['review_rate']}")
            print("scenario:", " ".join(f"{k}={v}" for k, v in m["by_scenario"].items()))
            for e in m["errors"]:
                print("  MISS", e)
            report["results"].append({"config": tag, **res, **m})
    if args.save:
        out = ROOT / "artifacts" / "eval"
        out.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = out / f"eval_{args.split}_{stamp}.json"
        path.write_text(json.dumps(report, indent=2))
        print(f"\nsaved {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
