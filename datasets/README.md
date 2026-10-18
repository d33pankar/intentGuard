# Synthetic WTS benchmark (`wts_benchmark.jsonl` + `manifest.json`)

62 hand-written call transcripts with customer-intent gold labels. Built
because no public dataset matches the WTS task (polite deflection,
agent-positive/customer-negative splits, bare replies); per the spec,
results on it measure *dataset* performance, never real-world conversion.

## Label rule (the annotation contract)

- **INTERESTED** — the customer explicitly commits or agrees to a concrete,
  agent-owned next step ("sign me up", "call me Tuesday at 3", "send it").
- **DISENGAGED** — the door is closed: explicit rejection or an explicit
  do-not-contact request.
- **UNCERTAIN** — vague deferral ("I'll think about it", "try me next
  month"), timing blocks, thin/bare replies, or contradictory signals a
  human must arbitrate. When in doubt we label UNCERTAIN: abstention is
  always safer than a forced call.

## Scenarios (spec §9.3)

`clear_interest` · `explicit_rejection` · `polite_deflection` ·
`not_now` (timing blocks; concrete callbacks are INTERESTED) ·
`contradictory` (mixed signals → UNCERTAIN unless the closer decides) ·
`varied_style` (terse, verbose, Hinglish/code-mixed, indirect) ·
`opt_out` (must trigger the deterministic rule, never the model) ·
`thin_reply` (bare yes/no → abstain, even a bare "No").

## Splits and the frozen-test rule

`manifest.json` (seed 42, stratified per scenario): **22 train / 17 val /
23 test**. Tune prompts, weights, and thresholds on **val**; report final
numbers on **test**; never tune on test. Train is reserved for the M6
fine-tune. `tests/unit/test_benchmark.py` enforces schema, partition
cleanliness, and no leakage into the baseline training corpus.

## Running it

```bash
make eval            # test split: baseline + hf-zeroshot/direct
make eval-full       # + literal and role styles
```

Expect: `accuracy`, `macro_f1`, 3×3 confusion matrix, `false_stop`
(interested → stopped: the costly error), `false_continue`, `review`
rate, per-scenario accuracy, and every miss with its score.
`--save` writes a timestamped JSON report to `artifacts/eval/` (gitignored).
