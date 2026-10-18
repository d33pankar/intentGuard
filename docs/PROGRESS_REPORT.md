# IntentGuard — Progress Report

**Date:** 2026-10-18 · **Commit:** `9c71dcb` (main) · **Tests:** 73/73 passing
**Spec:** `docs/PROJECT_SPEC.md` (v1.0, 2026-10-13) · **Thesis:** *Design and Evaluation of a Cloud-Native, Cost-Sensitive Customer Disengagement Detection Framework Using Large Language Models* (M.Tech Cloud Computing, IIT Patna)

---

## 1. End-to-end plan (what the product is supposed to become)

**Product idea.** IntentGuard implements the When-To-Stop (WTS) workflow: analyse customer communications, estimate interest/disengagement, and recommend whether a campaign should keep contacting a customer. Recommendations use exactly three states — `Interested` (continue), `Not interested` (stop), `Not contacted` (no contact history; never a model output) — plus an explicit human-review state for uncertain evidence. Explicit opt-outs are a deterministic rule, never a model judgment.

**V1 contract (the first shippable).** A user manually uploads one transcribed call (`.txt`), supplies a customer (`MID`) and product, and gets an immediate score + recommendation that is persisted; a read-only dashboard shows the latest result per customer–product. No schedules, no live calls, no cloud.

**Full roadmap after V1** (spec §2.4, milestones §12):

| Stage | Content |
|---|---|
| 2 — Automated batch ingestion (M5) | Hourly pickup of transcript/contact files from storage (local folder → S3), validation, dedup, idempotent scoring, job tracking, queue/worker when needed |
| 3 — Customer/product profiling (M4) | Fixed-format customer master, MID-first resolution, ≤5 phones/emails, `contact_attempts` with unique event IDs, first/last contact timestamps, replay-safe metrics |
| 4 — Domain model (M6) | Labelled public/synthetic benchmark, frozen baselines, fine-tuned classifier, same held-out test set, honest reporting (H1) |
| 5 — Decision intelligence (M7) | Email + feedback-form channels, fusion (average → weighted → learned), explicit cost matrix, cost-sensitive thresholds, review band (H2, H3) |
| 6 — Cloud deployment (M8) | Costed AWS plan → EC2/Docker, S3, Postgres/RDS, queue, CloudWatch, secrets, HTTPS/auth; local-vs-cloud latency/throughput/cost comparison (H4) |
| 7 — Live scoring (M9) | Incremental timestamped segments, running estimate, live UI timeline, stability/latency measurement |
| 8 — Call-platform integration (M10) | Telephony integration with consent, streaming ASR + speaker turns, SDK/API, Docker image, versioned artifacts |
| 9 — Production readiness (M10) | Auth, audit logs, monitoring, tenant isolation, drift checks, controlled evaluation on legitimate outcome data |

**Research spine.** H1 fine-tuned intent vs baselines on polite deflection · H2 cost-based thresholds vs accuracy thresholds · H3 fusion vs averaging under missing channels · H4 async batch resilience local vs cloud. RQ1–RQ4 mirror these. Thesis chapters 1–8 draw on the implementation + experiments (§15).

---

## 2. What is achieved (working, tested, demoed live)

**Milestones M0–M2 — complete (and exceeded).**
- M0: repo inspected, environment recorded, spec kept at `docs/PROJECT_SPEC.md`.
- M1: upload UI (`.txt`, size/type validation), MID + product supply, replaceable `IntentScorer` interface, synchronous scoring with evidence, uncertainty/errors never labelled `Not contacted`, `/health` + `/ready`, tests over interface + decisions.
- M2: PostgreSQL 17 star schema (`mid_registry`, `dim_customer`, `customer_identifiers`, `dim_product`, append-only `fact_<product>` + `v_<product>_latest` views, auto-provisioned per catalogue product), latest-result persistence, read-only dashboard (KPIs, resolution doughnut, histogram, 14-day activity, sortable table — beyond the spec's minimum columns).

**M3 (hardening) — mostly done.** Input limits, no raw text in logs, frozen 22-line baseline corpus + 12 polite-deflection probes in tests, honest limitation docs in README, `.env.example`, 73 tests. Missing: runnable eval scripts + dataset manifests (`datasets/synthetic/` is empty).

**M4 (identity/history) — partially done.** MID-first resolution, exact phone/email reuse, 409 conflicts that record nothing, ≤5 identifiers/type, `call_date` on facts, append-only history. Missing: `contact_attempts` table with unique event IDs/outcomes, derived first/last-contact timestamps, replay-idempotency proof.

**Beyond-spec extras (all live-verified, all tested):**
- **Pluggable HF model** (`app/inference/registry.py`, one-line future registration) with **selectable prompt styles** — `direct` (5/5 probes), `literal` (4/5, warns), `role` (4/5, experimental) — chosen in the UI dropdown, recorded per result.
- **Customer-only scoring** (`scored_scope`): agent hype excluded; **bare yes/no abstains** to review (`insufficient_signal`); opt-out rule shared by every model.
- **Structured evidence**: verdict + collapsible prompt + speaker-attributed cue cards + weak-signal footnotes.
- **UI**: Ingest (3-3-1 field hierarchy, gated scoring, template download) · Dashboard · About tabs.

**Research so far.** Zero-shot vs baseline compared on 5 probes with a published scorecard (direct 5/5; polite brush-off and engaged-call cases both flip correctly vs baseline). Per spec §9 ("hypotheses, not claims"), this is exploratory, not an H1 result — no frozen test set, no fine-tuned model yet.

---

## 3. What is left (in recommended order)

1. **Eval harness + labelled benchmark (starts M3/M6).** Fill `datasets/synthetic/` with the five scenario categories (clear interest, rejection, polite deflection, not-now, contradictory, channel disagreement, opt-outs), train/val/test splits with leakage guards, frozen manifests, runnable `eval` command reporting macro F1, confusion matrix, false-stop/continue rates, polite-deflection subset. *This unblocks every research claim.* ✅ **DONE 2026-10-18** — 62 items, 23-test frozen manifest, `make eval`, first numbers in README (baseline 0.65 > zero-shot 0.48; honest miss list included).
2. **M4 remainder.** `contact_attempts` + outcomes, first/last-contact derivation, replay tests.
3. **Migrations.** Replace `create_all` with Alembic (spec explicitly asks).
4. **M7 decision work.** Email/feedback inputs, fusion ladder, explicit cost matrix + threshold selection on validation data (H2, H3).
5. **M6 fine-tune** on the benchmark vs frozen baselines (H1, RQ1).
6. **M5 ingestion.** Storage adapter (local dir), hourly schedule, dedup/idempotency, job tracking; worker/queue only if needed (H4 needs the batch path to exist).
7. **Docker Compose + local/AWS parity (M8/M10-local).** `api`, `worker`, `postgres`, `redis`, dashboard; reproducible measurements.
8. **M8 cloud** (needs explicit cost approval first), **M9 live scoring**, **M10 audio + packaging** — all future scope.
9. **Thesis chapters.** Nothing written yet; chapters 4–6 depend on items 1–5.

**Known deviations from spec to revisit:** no Alembic; no Redis/Docker (no Docker on this machine); SQLite fallback in play locally; `to_stop` semantics kept; no real/suppression data anywhere (synthetic only — as required).

**Top risks.** (a) Prompt/style rankings rest on 5 hand probes — do not generalise them. (b) No multi-channel data yet, so H3/M7 are design-only. (c) Zero-shot runs in-process on CPU — fine for prototype, must move to a worker/GPU before any scale claim.
