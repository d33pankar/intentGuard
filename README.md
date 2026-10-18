# IntentGuard

*Understand intent. Make smarter outreach decisions.*

IntentGuard implements the WTS (When-To-Stop) workflow: it scores customer
communications for disengagement and recommends whether outreach should
continue. Academic context: M.Tech Cloud Computing, IIT Patna.

> Full specification: [`IntentGuard_Project_Specification_and_Agent_Guide (1).md`](./IntentGuard_Project_Specification_and_Agent_Guide%20(1).md)
> (canonical copy being moved to `docs/PROJECT_SPEC.md`).

## V1 contract (current)

Manually upload one `.txt` call transcript + `MID` + `product_id` →
immediate WTS result in the same interaction. No scheduler, no queue,
no cloud resources.

## Setup

Requires Python 3.11+ (tested on 3.12).

```bash
# install deps (or: pip install -e ".[test]" inside a venv)
pip install --target=./.deps -e . 2>/dev/null || pip install -e ".[test]"

# point at Postgres (copy .env.example -> .env and fill in; .env is gitignored)
# DATABASE_URL=postgresql+psycopg://user:pass@host:5432/intentguard_dw
# Without DATABASE_URL the app falls back to local SQLite automatically.

# run the API (DB tables + views are created on startup)
PYTHONPATH=./.deps uvicorn app.main:app --reload --port 8001
# or: make run
```

Open http://localhost:8001/ for the web UI, or http://localhost:8001/docs
for the interactive API.

## Usage

The web UI (`/`) has two tabs: **Ingest** (dropzone upload + identifiers +
product dropdown, one transcript at a time) and **Dashboard** (product
dropdown → performance KPIs, resolution doughnut, score distribution,
14-day activity → all latest scores, all read-only).

```bash
# health / readiness
curl localhost:8001/health
curl localhost:8001/ready

# score one transcript (valid .txt, non-empty, UTF-8, <=200 KiB)
curl -X POST localhost:8001/v1/score \
  -F "file=@call.txt;type=text/plain" \
  -F "phone=+91 98765 43210" \
  -F "email=someone@example.com" \
  -F "full_name=Full Name" \
  -F "address=Patna, Bihar" \
  -F "product_id=product_b"   # optional, defaults to product_b

# results + aggregates for a product (read-only — never runs inference)
curl localhost:8001/v1/products/product_b/results
curl localhost:8001/v1/products/product_b/metrics
curl localhost:8001/v1/products   # catalogue for the dropdowns
```

Example response:

```json
{
  "mid": "SYN_CUSTOMER_001",
  "product_id": "SYN_PRODUCT_001",
  "label": "DISENGAGED",
  "interest_score": 0.15,
  "decision_status": "DECIDED",
  "engine_resolution": "Not interested",
  "to_stop": true,
  "evidence": "Cues: not interested, ... Excerpt: '...'",
  "model_version": "baseline-tfidf-lr-v1",
  "opt_out_detected": false
}
```

## Transcript validation rules

A transcript scores **only when all seven fields are filled**:

`product_id` · `product_name` · `date_of_call` · `customer_name` ·
`customer_phone` · `customer_email` · `customer_address`

- On upload, `POST /v1/extract` tries to fill them from the transcript
  (a `Key: value` header block if present, else in-text cues like
  “my name is …”, phone/email patterns, dates). Found fields show green,
  missing ones amber — the user completes them inline.
- The Score button stays disabled until all seven are non-empty.
- The server re-validates everything on `POST /v1/score`: unknown product,
  name/catalogue mismatch, unparseable or future date, invalid phone/email
  all return **400 naming the offenders**, and nothing is recorded.
- A “Download header template (.txt)” link in the UI gives uploaders the
  ideal format; free-form transcripts work too, with manual completion.

## Star schema (Postgres: `intentguard_dw`)

Fact tables are **append-only** — one row per scored transcript, history is
never rewritten. The dashboard reads the latest event per MID through the
`v_product_{a,b}_latest` views.

```text
mid_registry            ── identity spine (MID-000001, …; system-assigned)
dim_customer            ── attributes per MID (full_name, address)
customer_identifiers    ── normalized phone/email → MID (match keys)
dim_product             ── catalogue (product_a, product_b)
fact_product_a          ── scoring events, Product A (historical channel)
fact_product_b          ── scoring events, Product B (current transcripts)
```

Any further catalogue product (e.g. `AMEX_BB_CC`) gets its own
`fact_<product>` table + latest view **auto-provisioned** on startup and on
first score — adding a product never needs a code change.
## Identity resolution

Every transcript carries some of: **phone, email, name, address**. The MID
is always assigned by us, never trusted from input.

- Exact phone or email hit → **matched**, record left untouched, scoring proceeds.
- Phone + email hit *different* MIDs → **409 conflict**, flagged for human review, nothing recorded.
- No hit → **new** customer (`MID-0000N`), identifiers stored (max 5 per type).
- A known `MID` may be passed explicitly to skip matching.
- New transcripts score into **Product B** by default (`DEFAULT_PRODUCT_ID`).

Legacy V1 SQLite data was migrated once via `scripts/migrate_sqlite_to_pg.py`
(customers kept their MIDs; their scores adopted as Product A history).

## Scoring models (pluggable)

`POST /v1/score` takes a `model` field; `GET /v1/models` lists the dropdown.
New models plug into `app/inference/registry.py` (one line) — see its docstring.

| Model | Behind it | Custom prompt? |
|---|---|---|
| `baseline` (default) | TF-IDF + Logistic Regression, instant, deterministic | No |
| `hf-zeroshot` | DeBERTa-v3 NLI zero-shot over a configurable hypothesis prompt | **Yes** — pick a style in the UI / `prompt_style` field: `direct` (default), `literal`, `role`. `HF_PROMPT_STYLE` sets the default; `HF_HYPOTHESIS_TEMPLATE` / `HF_INTERESTED_LABEL` / `HF_DISENGAGED_LABEL` reword `direct` |

Measured on 5 probes (polite brush-off, clear yes, soft no, brochure
request, engaged David call — scored customer-only, as shipped):

| Style | Result |
|---|---|
| `direct` | 5/5 |
| `literal` | 4/5 — auto-stops the engaged call (0.39); strict bar, compare only |
| `role` (role-framed, experimental) | 4/5 — false-continues the polite brush-off (0.78) |

A bare yes/no never reaches any model: fewer than three substantive
words abstains to `UNCERTAIN` 0.5 with `insufficient_signal: true`
("Are you over 20?" → "Yes" is not intent).

```bash
pip install -e ".[hf]"   # transformers + torch (CPU)
```

The HF model downloads (~350MB) on first use and runs in-process on CPU —
fine for prototyping; the explicit opt-out rule applies identically to every
model. `model_version` on every score/result row records which model decided.
Only the conversation text is scored — a leading `Key: value` header block is
stripped first (a header-only file is rejected with 400), and the default
disengaged hypothesis is worded to catch soft "call me later" brush-offs.
When turns are labelled (`Agent:` / `Customer:`, even inline on one line),
only the customer's utterances reach the model (`scored_scope: customer`);
agent hype can no longer inflate the score. Unlabelled transcripts fall
back to the whole conversation (`scored_scope: whole`).

## Meaning of scores

- `interest_score` 0.0–1.0: higher = more estimated interest. It is a
  **score, not a calibrated probability**.
- `INTERESTED` (≥ 0.6) → `Interested` (continue); `DISENGAGED` (< 0.4) →
  `Not interested` (stop); in-between → `UNCERTAIN` → `REQUIRES_REVIEW`
  with `engine_resolution: null` — a human must look at it.
- `Not contacted` is a **contact-history state**, never a model output.
  Errors (4xx/5xx) never produce a decision at all.
- Explicit opt-out phrasing ("do not call me", …) triggers a deterministic
  rule → `DISENGAGED` with `opt_out_detected: true`.

## Known baseline limitations (honest)

`baseline-tfidf-lr-v1` is a TF-IDF + Logistic Regression model trained on
22 unambiguous synthetic sentences. It separates those 22/22, but on 12
held-out polite-deflection probes only ~5 land `UNCERTAIN` — e.g. *"Thank
you for the information. I will contact you if I decide to proceed."*
scores ~0.70 `INTERESTED` (a false-continue). Polite deflection is exactly
research hypothesis H1 for the future fine-tuned model. Do not use this
baseline for real suppression decisions.

## Tests

```bash
PYTHONPATH=./.deps python -m pytest tests/ -q
# or: make test
```

## Benchmark (frozen synthetic set, 62 items)

```bash
make eval        # test split: baseline + hf-zeroshot/direct
make eval-full   # + literal and role styles
```

62 hand-labelled transcripts across 8 scenarios (see `datasets/README.md`
for the annotation rules), split 22 train / 17 val / **23 test** in a frozen
manifest. Tune on val, report on test, never tune on test. First test-split
numbers (2026-10-18): baseline acc **0.65** (macro F1 0.58, review rate
0.57, zero false stops/continues); hf-zeroshot/direct acc **0.48**
(false-stop 1, polite-deflection 0.0 — deferrals collapse to DISENGAGED
outside the 0.4–0.6 review band). The 5-probe story did not generalise:
zero-shot is over-decisive where it should abstain. Next loop: widen/recalibrate
the review band and reword deferral handling on **val**, then re-report.

## Roadmap

- ✅ Milestone 0 — repo/environment inspection (this machine: Python 3.12,
  no Docker/Postgres → SQLite default deferred to M2; no Redis in V1)
- ✅ Milestone 1 — synchronous scoring API (persisted from the UI build on)
- ✅ Milestone 4 (core) — Postgres star schema (`intentguard_dw`),
  deterministic identity resolution (MID assignment, conflict flagging),
  append-only product fact tables + latest views, legacy data migrated
- next: Alembic migrations, Streamlit/operator dashboard, hourly ingestion
