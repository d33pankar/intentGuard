# IntentGuard: Project Specification and Agent Implementation Guide

**Project:** Explainable, Cost-Sensitive Customer Disengagement Detection  
**Academic context:** M.Tech Cloud Computing, IIT Patna  
**Document type:** Engineering specification, architecture plan, research plan, and implementation backlog  
**Status:** Initial project baseline  
**Version:** 1.0  
**Date:** 2026-10-13

---

## 1. Instructions for the Coding Agent

You are the implementation agent for **IntentGuard**, a customer-disengagement detection and outreach-decision tool based on the original WTS (When-To-Stop) workflow described in this document.

Build the project incrementally as a working, tested, maintainable software system. Treat this file as the initial source of truth. Before making significant architectural changes, explain the reason and update this document or the relevant design record.

### Required working style

1. Inspect the repository and the current runtime environment before modifying anything.
2. If a repository already exists, preserve useful work and adapt it rather than blindly replacing it.
3. Implement one milestone at a time. Keep the application runnable at the end of every milestone.
4. Write complete code, configuration, database migrations, tests, and setup instructions. Avoid placeholder functions in functionality claimed as complete.
5. Run tests and relevant lint/type checks after changes. Report commands executed and their actual results.
6. Never claim a test, deployment, migration, or cloud operation succeeded unless it was actually run and verified.
7. Keep secrets out of source control. Provide `.env.example`, not a populated `.env`.
8. Prefer simple, observable, well-tested components over premature microservices or Kubernetes.
9. Do not add paid cloud resources, incur charges, publish services to the public internet, or delete data without explicit user approval.
10. Do not use confidential employer/client data. Use public datasets whose licenses permit the intended use, or clearly labeled synthetic data.
11. Keep research claims separate from engineering assumptions. Do not invent evaluation results or claim synthetic-data performance establishes real-world effectiveness.
12. When blocked, explain the blocker and offer the smallest safe next step.

### First response from the agent

Before implementing, report:
- Repository path and current structure.
- Existing relevant files and services.
- Runtime and tool versions available.
- Proposed first milestone.
- Any blocking assumptions or conflicts with this specification.

Then proceed with the first milestone unless essential information or approval is missing.

---

## 2. Project Overview

**Product name:** IntentGuard  
**Tagline:** *Understand intent. Make smarter outreach decisions.*  
**Repository name:** `intentguard`  
**Origin:** Based on the original When-To-Stop (WTS) workflow  
**Academic thesis title:** *Design and Evaluation of a Cloud-Native, Cost-Sensitive Customer Disengagement Detection Framework Using Large Language Models*

Use **IntentGuard** as the product and software-project name throughout the implementation, README, dashboard, API documentation, screenshots, and demo materials. Retain **WTS (When-To-Stop)** when describing the original business workflow or historical context, and in thesis sections where that terminology is technically or academically relevant. Do not rename existing database fields such as `toStop` or `to_stop` without a deliberate migration decision. The product name and thesis title serve different purposes.

WTS analyzes customer communications to estimate customer interest/disengagement and recommend whether a campaign should continue contacting a customer.

The product is named **IntentGuard**; WTS (When-To-Stop) is the decision workflow it implements. Development is staged so the first release is a usable application before automated pipelines are introduced.

**V1 contract:** a user manually uploads one already-transcribed call transcript, selects or supplies a `MID` and product, and receives an immediate WTS result. The result is persisted to the product-level records. A read-only dashboard queries the product-level table (or a read-only view over it) and displays `MID`, `fname`, `lname`, and `engine_resolution`. V1 does not ingest files on a schedule and does not connect to live calls.

The initial scoring workflow focuses on call transcripts. Email and feedback-form scoring, multi-channel aggregation, and hourly storage ingestion are later stages. Use public or synthetic data only. Do not connect the prototype to real customer suppression workflows without appropriate authorization, validation, compliance review, and operational controls.

### 2.1 Main objectives

1. Deliver a working V1: manually upload a transcript and immediately see the WTS result.
2. Persist the scored customer-product result so the dashboard can display it.
3. Keep the dashboard read-only; it must not run inference or mutate records.
4. Maintain a clear separation between customer identity, product catalogue, contact events, model assessments, and product-level recommendations.
5. Establish reproducible pretrained-model baselines and document their errors.
6. Add automated hourly ingestion only after V1 works end to end.
7. Fine-tune a domain-specific model and evaluate it against frozen baselines in later research stages.
8. Add cloud deployment and real-time transcript scoring as later stages, not V1 dependencies.
9. Produce reproducible experiments and documentation for the M.Tech thesis.

### 2.2 V1 scope and acceptance criteria

V1 must include:
- A simple web UI for manually uploading a plain-text (`.txt`) call transcript.
- A required `MID` and product selection/identifier associated with the transcript.
- Synchronous scoring for one transcript, with a result returned in the same user interaction.
- A baseline pretrained/classification model behind a replaceable inference interface.
- A visible WTS recommendation and score, plus a short evidence/explanation field where supported.
- Persistence of the latest result for that `(MID, product_id)` combination.
- A read-only dashboard that queries the product-level records and displays at least `MID`, `fname`, `lname`, and `engine_resolution`. It may show product name and last-evaluated time as useful supporting columns.
- Clear validation and processing-error messages. A failed upload or inference must not be labelled `Not contacted`.
- Local startup instructions and automated tests for the complete upload-to-dashboard workflow.

V1 should use a small, understandable deployment. Do not add Redis, a scheduled worker, S3, AWS resources, live transcription, or a complex microservice architecture just to complete V1. A database is required to persist the product result and serve the dashboard; the customer and product tables can be minimal.

### 2.3 Recommendation semantics

The product-level `engine_resolution` must use these exact user-facing values:
- `Interested`: available scored evidence supports continued engagement.
- `Not interested`: available evidence supports disengagement or rejection.
- `Not contacted`: no qualifying contact/exposure record exists for this customer-product combination.

`Not contacted` is a contact-history state, not a model prediction. A missing transcript, invalid upload, inference error, or uncertain model output must not be converted into `Not contacted`. If a transcript was processed but evidence is insufficient or contradictory, surface an explicit review/uncertain state in the scoring result; do not force it into one of the three statuses without a documented policy. Explicit opt-outs must be handled as a separate deterministic rule in future decision logic.

### 2.4 Main future stages

- **Stage 2, automated batch ingestion:** periodically read new transcript and contact-attempt files from a configured storage location, initially every hour; validate, deduplicate, score, and update product-level records.
- **Stage 3, customer/product profiling:** use `MID` as the canonical customer key. Keep a fixed-format `customer_master` with agreed fields and up to five valid phone numbers and five valid email addresses selected in source order. Do not build identity enrichment or ranking; use the first five valid values. Resolve by MID first and use phone/email as secondary identifiers, flagging conflicting matches for review.
- **Stage 4, domain-specific model:** fine-tune an appropriate pretrained model using a documented labelled dataset and compare fairly with V1 baselines on the same held-out test set.
- **Stage 5, decision intelligence:** evaluate cost-sensitive thresholds, missing-channel handling, and channel fusion when email and feedback support is introduced.
- **Stage 6, cloud deployment/evaluation:** deploy to AWS only after local validation and explicit cost approval; measure throughput, latency, resilience, and actual cost.
- **Stage 7, live transcript scoring:** accept incremental timestamped transcript segments and update engagement estimates during a conversation.
- **Stage 8, call-platform integration:** add speech recognition and one supported calling/contact-centre integration, with required consent and authorization.
- **Stage 9, packaged software:** provide a reusable Python SDK/API, Docker image, versioned model artifacts, installation guide, authentication, and deployment documentation.
- **Stage 10, production readiness:** add appropriate tenant isolation, auditability, monitoring, model drift checks, and controlled evaluation from legitimate outcome data.

These stages are a roadmap, not a requirement to build everything before the M.Tech deliverable. V1 and the approved research contribution take priority.

---

## 3. Proposed Technology Stack

Use these as defaults. Inspect the repository first and explain any material deviations.

| Area | Initial choice | Notes |
|---|---|---|
| Language | Python 3.11 or a compatible supported version | Pin dependencies |
| API | FastAPI | Versioned REST endpoints |
| Data validation | Pydantic | Strict input schemas |
| Database | PostgreSQL | Persistent metadata, scores, decisions |
| Migrations | Alembic | Schema changes must be versioned |
| Queue | None in V1 | Add Redis with RQ or Celery only for the later hourly/asynchronous pipeline; pick one, not both |
| Worker | None required in V1 | Add a separate Python worker for later asynchronous processing |
| Baseline ML | scikit-learn | TF-IDF + Logistic Regression |
| Transformer fine-tuning | Hugging Face Transformers, optional later milestone | Avoid loading a large model in the API process |
| Data processing | Pandas initially | Add PySpark only if justified by measured workload/research |
| Dashboard | Streamlit | Simple operator/research UI |
| Object storage | None required for V1 transcript retention | Add a storage adapter for hourly file ingestion and S3 later; avoid retaining raw transcripts by default |
| Containers | Docker Compose | Local reproducible deployment |
| Tests | pytest | Unit, integration, API, and workflow tests |
| Observability | Structured logs and health endpoints first | Prometheus/Grafana later if useful |
| Cloud | AWS EC2 + S3 initially | Optional RDS/managed queue as budget permits |

Do not introduce extra services simply because they are available. Keep the first release easy to run on a modest local server without a GPU.

---

## 4. System Architecture

### 4.1 Logical flow

**V1, manual upload and immediate result:**

```text
User uploads TXT + supplies MID/product
                |
                v
         Upload/scoring UI
                |
                v
       Validate transcript + keys
                |
                v
      WTS inference and decision
                |
                v
 Persist product-level result in PostgreSQL
                |
                v
 Read-only dashboard queries product records
 and displays MID, fname, lname, engine_resolution
```

**Later, hourly batch pipeline:**

```text
Configured storage location
        -> hourly scheduler
        -> discover/validate/deduplicate files
        -> processing queue and worker
        -> WTS inference and decision engine
        -> update product-level records and history
        -> read-only dashboard
```

**Future live mode:** a supported call platform or transcript stream feeds incremental text to the same replaceable inference/decision interfaces. Live audio capture and speech recognition are not V1 requirements.

### 4.2 Architectural rules

- In V1, a single uploaded transcript is scored synchronously so the user sees the result in the same interaction. For later large batches, the API registers work and returns a batch/job identifier rather than processing the whole batch synchronously.
- The worker performs inference and updates persistent processing states.
- PostgreSQL is the source of truth for job and decision status. Redis is a queue, not the only record of work.
- Store large raw artifacts in object storage or a controlled filesystem and store references in PostgreSQL.
- Each communication gets an independent assessment.
- Aggregation occurs at a defined key: `(customer_ref, campaign_ref, window_id)`.
- Do not mix communications from different campaigns or assessment windows.
- A decision must record exactly which channel assessments contributed.
- Late-arriving channel data may create a new decision version; never silently rewrite history.
- Use a defined cutoff or readiness policy so the system does not wait forever for a rare feedback form.
- Enforce idempotency for repeated submissions and retries.
- Never make a real customer-contact action as a side effect of inference.

---

## 5. Ingestion Requirements

### 5.1 Supported formats

For the initial release:
- JSON request payloads.
- JSONL files for batches.
- CSV files where the schema is clear.
- TXT for a single call transcript.
- Manual feedback submission through the dashboard can be added after the API workflow works.

Support `.eml`, mailbox APIs, audio files, and live transcription only in later milestones.

### 5.2 Example communication record

```json
{
  "customer_ref": "SYN_CUSTOMER_001",
  "campaign_ref": "SYN_CAMPAIGN_001",
  "window_id": "2026-10",
  "interaction_ref": "SYN_CALL_001",
  "channel": "call",
  "event_time": "2026-10-13T10:30:00Z",
  "text": "Thank you for the information. I will contact you if I decide to proceed.",
  "speaker_segments": [
    {
      "speaker": "agent",
      "text": "Would you like to schedule a follow-up?"
    },
    {
      "speaker": "customer",
      "text": "Thank you for the information. I will contact you if I decide to proceed."
    }
  ],
  "metadata": {
    "dataset": "synthetic_v1"
  }
}
```

The `text` field is the canonical text analyzed by the model. `speaker_segments` are optional metadata for future analysis. Never assume diarization has identified the customer correctly unless the source guarantees that mapping.

### 5.3 Validation

Validate:
- Required identifiers are non-empty.
- `channel` is one of `call`, `email`, or `feedback`.
- `event_time` is a valid timezone-aware timestamp.
- Text is non-empty after normalization and within a configurable size limit.
- Batch record count and upload size are bounded.
- Extra fields are handled consistently.
- No raw secrets or credentials are accepted in metadata.
- Customer references in the research environment are synthetic or appropriately anonymized.

Reject malformed records with clear error details. For a batch, support partial acceptance where safe and report valid/invalid counts. Do not log full communication text by default.

### 5.4 Deduplication and idempotency

Use an idempotency key or a deterministic source identity. A reasonable initial identity is based on source-provided `interaction_ref`, channel, and customer/campaign/window, but avoid relying only on text hashes when two legitimate communications could have identical text.

Repeated submissions must not create duplicate assessments or double-count a channel in aggregation. Return existing identifiers for recognized duplicates when appropriate.

### 5.5 Ingestion lifecycle

1. Receive request/file.
2. Validate schema and size.
3. Register batch and communication records in PostgreSQL.
4. Store raw file/artifact safely where needed.
5. Enqueue pending communication IDs.
6. Worker claims a job and marks it `PROCESSING`.
7. Worker normalizes text and runs inference.
8. Worker persists an immutable/versioned channel assessment.
9. Aggregation evaluates customer channel coverage and readiness.
10. Decision is saved with contributing assessment IDs and policy version.
11. Batch summary is updated when all expected work reaches a terminal state.

---

## 6. API Contract

Use a `/v1` prefix. Exact response schemas should be implemented with Pydantic and documented in OpenAPI.

### V1 endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Basic liveness check |
| `GET` | `/ready` | Readiness check for dependencies actually used by V1 |
| `POST` | `/v1/score` | Accept one transcript plus MID/product identifiers and return the immediate scoring result |
| `GET` | `/v1/products/results` | Read-only list of product-level results for the dashboard, including MID/name fields via a read-only query/view |
| `GET` | `/v1/products/results/{result_id}` | Read one persisted customer-product result, if a result ID is used |

The upload UI may call the scoring service directly or use `POST /v1/score`; choose one clear implementation and document it. The dashboard must use read-only queries/endpoints and must not invoke inference or mutate records.

### Later-stage endpoints

Add only when the corresponding milestone is reached:
- `POST /v1/batches` to register an ingestion batch.
- `POST /v1/batches/{batch_id}/communications` to submit batch records.
- `POST /v1/communications` for automated single-communication ingestion.
- `GET /v1/batches/{batch_id}` for batch status and summary.
- `GET /v1/customers/{customer_ref}/decisions` for decision history.
- `GET /v1/decisions/{decision_id}` for decision details and contributing channels.
- `POST /v1/batches/{batch_id}/finalize` to close a batch/window.
- `GET /v1/metrics/summary` for dashboard aggregates.
- `POST /v1/feedback` for feedback-form ingestion.

### API behavior

- Batch submissions return a batch ID and accepted/rejected counts, not a synchronous inference result for the entire batch.
- Job status must be queryable.
- Return appropriate HTTP status codes and stable error structures.
- Use pagination for lists.
- Do not expose database internals or stack traces.
- Add authentication before exposing the service outside a trusted development network.
- Use request limits and rate limits for public endpoints.
- Generate an OpenAPI specification through FastAPI.

---

## 7. Data Model

Implement database migrations rather than creating schema ad hoc at runtime.

### 7.0 V1 minimum tables and ownership

V1 needs only the database structures required to upload, score, persist, and display results. Do not force the later batch/queue architecture into the first milestone.

**`customer_master`**
- `MID` (primary key)
- `fname`, `lname`, `dob` (nullable as appropriate)
- `phone1` through `phone5`
- `email1` through `email5`
- Additional agreed fixed profile fields only where available and needed
- `created_at`, `updated_at`

The source contract provides a maximum of five phone values and five email values. For each type, ingestion takes the first five valid values in source order. No ranking, enrichment, or attempt to discover more values is in scope. Normalize phone/email values for matching where practical. Match by MID first; secondary email/phone matches that point to different MIDs must be flagged for review rather than guessed.

**`products`**
- `product_id` (primary key)
- `product_name`
- Optional descriptive metadata and timestamps

**`customer_product_metrics`** (the product-level table queried by the dashboard; name can be `products` only if that matches an existing approved schema, but do not mix product catalogue rows with customer-specific metrics)
- Unique customer-product key, normally `(MID, product_id)`
- `engine_resolution`
- `interest_score` (nullable if the model does not provide a meaningful comparable score)
- `last_evaluated_at`
- Optional `model_version`, `decision_policy_version`, and short explanation/reference
- Contact metrics can be added when contact-attempt ingestion is implemented

The dashboard is read-only and must query this table or a read-only SQL view joining it with `customer_master` and `products`. The minimum displayed columns are `MID`, `fname`, `lname`, and `engine_resolution`; product name and last evaluation time are useful additions. The dashboard must not perform inference or write database records.

**V1 transcript processing**
- V1 can keep the uploaded transcript in memory for scoring and avoid retaining the raw text by default.
- Persist the resulting score/decision and minimal audit metadata needed to explain when it was generated and which model version was used.
- Do not create contact-attempt counts from transcript uploads unless a qualifying contact event is actually supplied.
- A failed upload or failed inference must not overwrite a prior successful result or create `Not contacted`.

**Later-stage tables**
- `contact_attempts`: individual successful and failed attempts, including attempts without transcripts; uniquely identify events to prevent double-counting.
- `communications`: source/channel text or secure artifact reference and provenance.
- `channel_assessments`: per-communication model output and model version.
- `customer_decisions`: versioned decision history and decision-policy metadata.
- `batches` and job-attempt tables: introduced with scheduled/batch ingestion, not required merely to make V1 work.


### 7.1 `batches`

Suggested fields:
- `id` UUID primary key
- `source_type`
- `status`
- `created_at`, `started_at`, `completed_at`
- `total_records`, `accepted_records`, `success_count`, `failure_count`
- `error_summary` (safe, non-sensitive)
- `dataset_version` (nullable)

### 7.2 `communications`

Suggested fields:
- `id` UUID primary key
- `batch_id` foreign key
- `customer_ref`
- `campaign_ref`
- `window_id`
- `interaction_ref`
- `channel`
- `event_time`
- `text` or controlled text reference, depending on storage policy
- `raw_object_uri` nullable
- `content_hash`
- `processing_status`
- `attempt_count`
- `created_at`, `updated_at`

Add appropriate unique constraints for source identity/idempotency. Index customer/campaign/window and batch/status lookups.

### 7.3 `channel_assessments`

Suggested fields:
- `id` UUID primary key
- `communication_id` foreign key
- `model_name`, `model_version`
- `label`
- `interest_score` nullable until a meaningful scoring contract is established
- `confidence` nullable; do not treat uncalibrated LLM self-confidence as probability
- `mood_label` optional
- `evidence` JSONB with short, input-grounded explanations
- `calibration_version` nullable
- `created_at`

A model prediction must not be overwritten when the model changes. Create a new assessment version or a new row.

### 7.4 `customer_decisions`

One record per decision version for `(customer_ref, campaign_ref, window_id)`.

Suggested fields:
- `id` UUID primary key
- `customer_ref`, `campaign_ref`, `window_id`
- `version` integer
- `to_stop` nullable Boolean
- `decision_status`: `DECIDED` or `REQUIRES_REVIEW`
- `aggregate_interest_score` nullable
- `threshold`
- `policy_name`, `policy_version`
- `model_version` or a record of per-channel model versions
- `reason_summary`
- `created_at`

Use a uniqueness constraint on `(customer_ref, campaign_ref, window_id, version)`.

### 7.5 `decision_channels`

Maps a decision to the exact contributing channel assessments:
- `decision_id`
- `assessment_id`
- `channel`
- `score_used`
- `weight_used`
- `availability_reason` or a separate coverage table if needed

### 7.6 Additional entities

Add only when needed:
- `job_attempts` for detailed retry history.
- `experiment_runs` for research experiment metadata.
- `dataset_manifests` for dataset provenance, licenses, splits, and checksums.
- `audit_events` for meaningful state/decision changes.

Do not store full customer text in application logs.

---

## 8. Decision Semantics and Scoring

### 8.1 Labels

Initial intent labels:
- `INTERESTED`
- `UNCERTAIN`
- `DISENGAGED`

These are labels for the research task, not guaranteed truth about eventual conversion. Define an annotation rubric and handle ambiguity explicitly.

### 8.2 Interest score contract

Define `interest_score` as a score where:
- `0.0` means lowest estimated interest.
- `1.0` means highest estimated interest.

Only call it a probability if it is calibrated and the calibration procedure is documented. Otherwise, call it a score.

### 8.3 Simple averaging baseline

For available channel set \(A\):

\[
S_{\text{interest}} = \frac{\sum_{c \in A} s_c}{|A|}
\]

where each \(s_c\) is a comparable channel interest score.

Baseline decision rule:

\[
\text{toStop} =
\begin{cases}
\text{true}, & S_{\text{interest}} < \tau\\
\text{false}, & S_{\text{interest}} \geq \tau
\end{cases}
\]

The threshold \(\tau\) must be configurable and selected on validation data using a documented policy. Do not hardcode a claimed production threshold.

### 8.4 Missing channels

- Aggregate only eligible, successfully assessed channels.
- Record which channels were available and which were missing.
- Do not treat missing feedback as a zero-interest score.
- Define a readiness/cutoff rule so assessments can finalize without waiting indefinitely.
- If no valid channel assessment exists, set `decision_status=REQUIRES_REVIEW` and `to_stop=null`.
- Support re-assessment when late-arriving data arrives, creating a new decision version.

### 8.5 Uncertainty and explicit opt-out

- A low-confidence or conflicting assessment may return `REQUIRES_REVIEW`.
- The initial research prototype should not trigger real-world contact suppression.
- Explicit opt-out or do-not-contact requests must be handled by a separate deterministic policy in any future operational deployment. They must not be overridden by an interest score.
- Every decision must include a concise explanation tied to actual input evidence, not a fabricated rationale.

### 8.6 Cost-sensitive policy

Define the experimental loss:

\[
L = C_{FS}N_{FS} + C_{FC}N_{FC}
\]

where:
- \(C_{FS}\): assumed cost of falsely stopping an interested customer.
- \(N_{FS}\): count of false-stop cases.
- \(C_{FC}\): assumed cost of falsely continuing outreach to a disengaged customer.
- \(N_{FC}\): count of false-continue cases.

Normalize loss per evaluated customer for comparisons. Evaluate several cost ratios and state that these are assumptions unless real business data supports them. Choose thresholds on validation data, not the held-out test set.

---

## 9. ML and Research Plan

### 9.1 Model progression

**Baseline 1:** TF-IDF + Logistic Regression using scikit-learn.

**Baseline 2:** Existing pretrained transformer used without WTS-specific fine-tuning.

**Proposed model:** Fine-tune a suitable pretrained text classifier on labeled intent examples.

**Decision variants:**
1. Simple average of available channel scores.
2. Fixed weighted average with weights selected on validation data.
3. Learned fusion model using scores and channel-availability indicators, if dataset size supports it.
4. Cost-sensitive threshold selection.
5. Optional review band for uncertain cases.

Do not train a large language model from scratch. Model choice should be based on validation results, available compute, licensing, and inference cost.

### 9.2 Research hypotheses

**H1: Intent detection.** A WTS-specific fine-tuned model improves disengagement classification compared with a general baseline, particularly on polite deflection.

**H2: Decision quality.** A threshold selected using an explicit cost function lowers expected decision loss compared with an accuracy-maximizing threshold.

**H3: Channel fusion.** Weighted or learned fusion improves decision quality over simple averaging under tested channel availability patterns.

**H4: Cloud architecture.** Asynchronous, retryable batch processing improves resilience under failure scenarios, with measurable latency/throughput trade-offs compared with a synchronous baseline.

These are hypotheses, not claims of established improvements. Report null or negative results honestly.

### 9.3 Dataset plan

Use:
1. Public dialogue, customer-support, or intent data only when the license allows research use and the labels are suitable.
2. A clearly labeled synthetic WTS dataset for controlled scenarios, especially polite deflection and missing-channel tests.

Synthetic scenario categories should include:
- Clear interest.
- Explicit rejection.
- Polite deflection.
- Uncertainty / “not now”.
- Mixed or contradictory intent.
- Different communication styles.
- Channel disagreement.
- Missing email or feedback.
- Explicit do-not-contact requests for testing deterministic safety handling.

Create train/validation/test splits that avoid template or near-duplicate leakage. Keep the test set untouched while tuning prompts, models, weights, and thresholds. Manually review a sample and report annotation disagreement where feasible.

Do not claim that synthetic results establish real-world conversion prediction or business uplift. Without real outcome labels, conclusions must be scoped to the evaluated datasets and labels.

### 9.4 Evaluation metrics

**Model:**
- Precision, recall, macro F1.
- Confusion matrix.
- False-stop rate.
- Brier score/calibration analysis if meaningful probabilities are produced.
- Separate results on the polite-deflection subset.

**Decision policy:**
- Normalized expected loss.
- False-stop and false-continue counts/rates.
- Performance by channel availability pattern.

**Cloud/operations:**
- Accepted/invalid records.
- Duplicate handling correctness.
- Job success/failure rate.
- Throughput and batch completion time.
- Queue wait time.
- API p50/p95 latency.
- CPU and memory utilization.
- Recovery time under controlled worker failure.
- Cost per batch for AWS tests, using actual billing/configuration data.

Use customer-level splits when customer identities are available. Otherwise, document the split limitations. Use repeated runs or confidence intervals where practical. Never fabricate metric values.

---

## 10. Cloud Deployment Plan

### 10.1 Local development

Use Docker Compose with:
- `api`
- `worker`
- `postgres`
- `redis`
- `dashboard`

Optional later:
- `prometheus`
- `grafana`
- `minio`

The first release can use a local artifact directory. Keep the storage interface modular so it can later use S3 without changing business logic.

### 10.2 AWS prototype

Initial architecture:
- EC2 running Docker containers.
- S3 for batch artifacts and model artifacts.
- PostgreSQL container for a disposable demonstration, or RDS for a more robust deployment if budget permits.
- Redis container for a prototype, or a managed queue/service if justified.
- CloudWatch logs and basic metrics.
- Secrets Manager or another secure secret mechanism for deployed secrets.
- HTTPS and authentication before exposing an interface publicly.

Do not provision resources until the user explicitly approves the cost and deployment plan. Provide a cost estimate based on current AWS pricing before creating paid resources. Add budget alerts where possible and shut down unused compute.

### 10.3 Local versus AWS experiment

Use the same:
- Dataset and data order.
- Model artifact and version.
- Preprocessing and decision policy.
- Batch sizes and worker concurrency where comparisons are intended.

Record hardware, region, instance type, configuration, and measurement procedure. Compare latency, throughput, resource use, failure recovery, and actual cost. Do not claim high availability without implementing and testing it.

---

## 11. Repository Structure

Use a modular monolith, not multiple independently deployed microservices. The tree below is a possible eventual structure; create only modules required by the current milestone. Redis/queue modules, batch workers, and live streaming modules are future-stage components, not V1 prerequisites.

```text
intentguard/
├── app/
│   ├── main.py
│   ├── api/
│   │   ├── routes/
│   │   └── schemas/
│   ├── core/
│   │   ├── config.py
│   │   ├── logging.py
│   │   └── security.py
│   ├── db/
│   │   ├── models.py
│   │   ├── session.py
│   │   └── migrations/
│   ├── ingestion/
│   │   ├── validation.py
│   │   ├── deduplication.py
│   │   └── storage.py
│   ├── queue/
│   │   └── tasks.py
│   ├── inference/
│   │   ├── interface.py
│   │   ├── baseline.py
│   │   └── model_loader.py
│   ├── decisions/
│   │   ├── aggregation.py
│   │   ├── policy.py
│   │   └── explanations.py
│   └── services/
├── dashboard/
│   └── app.py
├── datasets/
│   ├── README.md
│   ├── synthetic/
│   └── manifests/
├── experiments/
│   ├── configs/
│   ├── scripts/
│   └── results/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── api/
├── scripts/
├── docs/
│   ├── architecture.md
│   ├── research-plan.md
│   ├── data-dictionary.md
│   └── adr/
├── artifacts/
│   └── .gitkeep
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── alembic.ini
├── Makefile
└── README.md
```

The agent may refine this structure if the existing repository or selected queue library warrants it. Keep module responsibilities clear and avoid circular imports.

---

## 12. Implementation Roadmap and Acceptance Criteria

The order below is intentional: V1 must be a working upload-to-score-to-dashboard application before scheduled ingestion or cloud infrastructure is added. The coding agent must not skip ahead simply because later architecture is described elsewhere in this document.

### Milestone 0 — Repository and design inspection

Tasks:
- Inspect existing repository and environment before modifying files.
- Confirm Python, Docker, and Compose versions.
- Identify reusable code and existing database schema.
- Record any conflicts with this specification.
- Keep this specification in `docs/PROJECT_SPEC.md` in the repository.

Acceptance:
- Current structure and environment documented.
- No destructive changes.
- First implementation milestone is explicit.

### Milestone 1 — Working V1: manual transcript scoring

Tasks:
- Build a simple upload UI for one `.txt` call transcript.
- Require/select a `MID` and product.
- Validate empty, malformed, and excessively large files.
- Implement a replaceable inference interface and a baseline model.
- Return the score and WTS result immediately in the same interaction.
- Show model output and concise supporting evidence where available.
- Handle uncertain output and errors distinctly from `Not contacted`.

Acceptance:
- A user can upload a valid transcript and see a result without running a separate batch job.
- Invalid uploads produce a useful error.
- Inference failures are visible and do not create misleading decisions.
- Unit tests cover the scoring interface and decision mapping.

### Milestone 2 — Minimal database and read-only dashboard

Tasks:
- Add PostgreSQL and Alembic migrations, or an equally maintainable migration approach.
- Implement the minimal `customer_master`, `products`, and customer-product result table.
- Persist the scored result for the selected `(MID, product_id)`.
- Implement a dashboard that only reads from the product-level table or a read-only view.
- Display at least `MID`, `fname`, `lname`, and `engine_resolution`; product name and last evaluation time may also be shown.
- Ensure the dashboard never runs inference or writes customer/product records.
- Add synthetic seed data and local startup instructions.

Acceptance:
- End-to-end workflow works: upload -> score -> persist -> dashboard shows updated row.
- The dashboard query correctly joins customer names and product recommendation.
- `engine_resolution` uses `Interested`, `Not interested`, or `Not contacted` according to the semantics in Section 2.3.
- `Not contacted` is based on absence of qualifying contact evidence, not on missing files, failed processing, or an uncertain model result.
- Tests verify persistence, read-only dashboard behavior, and customer/product key validation.

### Milestone 3 — V1 hardening and reproducible baseline

Tasks:
- Add deterministic baseline evaluation scripts and dataset manifests.
- Record model/version/configuration and the evaluation split.
- Add input limits, safe logging, and error handling.
- Document known model limitations and baseline failures.

Acceptance:
- Baseline metrics can be reproduced from documented commands.
- No raw transcript text is written to logs by default.
- README explains setup, usage, limitations, and the meaning of scores.

### Milestone 4 — Customer identity and product-level contact history

Tasks:
- Finalize fixed-format `customer_master` fields.
- Accept the first five valid phone numbers and first five valid emails in source order.
- Resolve customer by MID first; flag ambiguous secondary matches.
- Add `contact_attempts` with unique event IDs and explicit outcomes.
- Derive first/last successful contact timestamps and successful/failed contact counts per `(MID, product_id)`.

Acceptance:
- Replayed contact events do not double-count.
- Unanswered and declined calls count as failed attempts.
- Only actual successful conversations update first/last contacted timestamps.
- Customer/product metrics can be rebuilt from contact-attempt history.

### Milestone 5 — Hourly storage ingestion and reliable batch processing

Tasks:
- Add a configurable storage adapter (local folder first; S3 later).
- Schedule discovery of new/changed files hourly.
- Validate and deduplicate files and records.
- Add a queue/worker only when needed for reliable asynchronous processing.
- Track job status, retries, partial failures, and processed-file identities.
- Score eligible transcripts and update customer-product records idempotently.

Acceptance:
- Only new or changed files are processed.
- Re-running the same input does not create duplicate events or double-count metrics.
- Failures are visible and retryable.
- The manual V1 workflow continues to work.

### Milestone 6 — Research evaluation and domain-specific model

Tasks:
- Establish a labelled public/synthetic benchmark and documented annotation rules.
- Compare TF-IDF + Logistic Regression and a frozen pretrained baseline.
- Fine-tune a suitable pretrained model if dataset size/quality and compute justify it.
- Use the same held-out test set and consistent evaluation conditions.
- Analyse difficult cases such as polite deflection, ambiguity, and conflicting signals.

Acceptance:
- Training, validation, and test splits are reproducible and leakage-aware.
- Metrics include macro F1, precision/recall, confusion matrix, and false-stop rate.
- Results are reported honestly; no improvement is claimed unless measured.

### Milestone 7 — Cost-sensitive decision policy and multi-channel fusion

Tasks:
- Add email and feedback-form inputs after call transcript V1 is stable.
- Compare simple averaging with alternative fusion approaches under missing-channel patterns.
- Define an explicit cost matrix and select thresholds using validation data.
- Preserve decision history, model version, policy version, and contributing evidence.
- Treat explicit opt-out as a separate deterministic rule.

Acceptance:
- Test-set evaluation compares policies without threshold leakage.
- Results include expected decision loss and false-stop/false-continue metrics.
- Missing channels are not silently treated as negative evidence.

### Milestone 8 — AWS deployment and cloud evaluation

Tasks:
- Prepare a costed deployment plan before creating resources.
- Deploy the validated local system to a small AWS environment with appropriate authentication and HTTPS.
- Use S3 for artifacts if justified; choose database and queue services based on cost and experiment needs.
- Measure throughput, latency, resource consumption, recovery, and actual cost.

Acceptance:
- User explicitly approves any paid resources before provisioning.
- Deployment and teardown are documented.
- Cloud measurements include environment/configuration details and repeatable procedures.
- No claim of high availability without implementation and tests.

### Milestone 9 — Real-time transcript scoring prototype

Tasks:
- Accept incremental, timestamped transcript segments.
- Maintain conversation state and update estimates as new turns arrive.
- Push score/evidence updates to a live UI.
- Measure update latency, score stability, and inference resource usage.

Acceptance:
- A replayed transcript can be streamed segment by segment and produces a visible score timeline.
- Final streaming output can be compared with batch output.
- Uncertainty and changing estimates are communicated honestly.

### Milestone 10 — Live audio integration and packaged product

Tasks:
- Integrate one supported telephony/contact-centre platform with authorization.
- Add streaming speech recognition and speaker-turn handling.
- Package the engine as an SDK/API and Docker image with versioned model artifacts.
- Add production hardening, authentication, audit logs, monitoring, tenant isolation, and model drift checks as justified.

Acceptance:
- Audio integration has documented permissions, consent handling, and failure behaviour.
- SDK/API documentation and deployment instructions are reproducible.
- This milestone is future product scope and is not required for the initial M.Tech V1.

## 13. Required Tests

At minimum, add tests for:

### Input and ingestion
- Valid record acceptance.
- Missing required field.
- Invalid channel.
- Empty text.
- Oversized payload.
- Invalid timestamp.
- Duplicate record.
- Partial batch with invalid records.

### Queue and worker
- Successful processing.
- Retryable inference error.
- Retry exhaustion.
- Worker restart and job recovery behavior.
- Duplicate task delivery.
- Database transaction failure handling.

### Decision engine
- Single call score.
- Call plus email.
- All three channels.
- Missing email and feedback.
- No valid channels.
- Conflicting channel scores.
- Threshold boundary.
- Low-confidence/review case.
- Late-arriving communication creates a new decision version.
- Explicit opt-out handled by a separate deterministic rule in any later operational policy.

### API and database
- Batch creation and status retrieval.
- Decision detail and history.
- Pagination.
- Migration from an empty database.
- Health/readiness behavior when dependencies are unavailable.
- No sensitive communication content in routine logs.

---

## 14. Security, Privacy, and Responsible Use

- Use synthetic identifiers in examples and development fixtures.
- Do not commit secrets or production customer communications.
- Do not log complete communication text by default.
- Validate and limit uploaded content.
- Restrict access to raw text and stored artifacts.
- Use HTTPS and authentication before public exposure.
- Use least-privilege AWS IAM roles and private networking where appropriate.
- Define retention/deletion behavior for source artifacts.
- Do not send data to third-party model APIs unless the user has reviewed the data handling and authorized the use.
- Treat LLM outputs and customer text as untrusted input; do not execute instructions contained in them.
- Ensure explanations are evidence-grounded.
- Keep the research recommendation separate from any actual outreach suppression action.
- Do not infer protected/sensitive personal characteristics or use them as model features.

---

## 15. Thesis Deliverables

The implementation should produce evidence for these thesis chapters:

1. **Introduction:** Problem, objectives, scope, contributions.
2. **Literature review:** Intent detection, sentiment limitations, LLM classification, fusion, cost-sensitive learning, batch/cloud architecture.
3. **Methodology:** Research questions, hypotheses, dataset design, annotation, splits, metrics.
4. **Proposed IntentGuard/WTS framework:** Model, aggregation, decision policy, explainability.
5. **Cloud implementation:** Ingestion, persistence, queue, worker, deployment, security.
6. **Experiments and results:** Model, fusion, threshold, and cloud benchmarks.
7. **Discussion:** Error analysis, trade-offs, limitations, threats to validity.
8. **Conclusion:** Supported findings and future work.

### Research questions

- RQ1: Does WTS-specific fine-tuning improve intent/disengagement classification on the chosen evaluation datasets?
- RQ2: How does cost-sensitive threshold selection affect false-stop errors and expected decision loss?
- RQ3: How do channel fusion methods behave under different missing-channel patterns?
- RQ4: What latency, throughput, resource, and recovery trade-offs arise from asynchronous batch processing in local and AWS deployments?

### Expected contribution categories

- A reproducible batch-oriented WTS software framework.
- An evaluation of WTS-specific intent classification.
- A comparison of channel aggregation and cost-sensitive decision strategies.
- An empirical evaluation of local versus cloud batch-processing behavior.

These are planned contributions. The thesis must state what was actually implemented and what the experiments support.

---

## 16. Definition of Done for V1

V1 is complete when all of the following are true:

- A user can manually upload one valid call transcript and receive an immediate WTS result.
- The user supplies/selects a valid MID and product.
- The result is persisted for the relevant customer-product combination.
- A read-only dashboard displays `MID`, `fname`, `lname`, and `engine_resolution` from product-level records (or a read-only view).
- `engine_resolution` supports `Interested`, `Not interested`, and `Not contacted` with the semantics defined in Section 2.3.
- Upload/inference errors and uncertain outputs are not misrepresented as `Not contacted`.
- Database migrations, configuration examples, setup instructions, and automated tests are included.
- Tests and commands actually run are reported accurately.
- Public/synthetic data is used for the demonstration.
- No scheduled hourly pipeline, real-time audio integration, paid cloud deployment, or real customer suppression is required to call V1 complete.

## 17. Immediate Next Actions

**Implement V1 only.** Start by inspecting the repository, then deliver Milestones 0–2 in small tested increments. Do not implement the hourly pipeline, fine-tuning, AWS deployment, or live-call features until the manual upload-to-score-to-dashboard path is working and verified.


The implementation agent should begin with the following order:

1. Inspect the existing repository and environment.
2. Create or update `docs/PROJECT_SPEC.md` with this specification.
3. Propose the exact initial dependency versions and repository structure.
4. Implement Milestone 1: runnable FastAPI, PostgreSQL, Redis, Docker Compose, configuration, health/readiness checks, README, and basic tests.
5. Run the application and tests; report the exact commands and outcomes.
6. Stop and summarize the working state before starting Milestone 2.

**Do not implement every milestone in one giant change.** Maintain a runnable, tested system at each stage and update this document when a design decision changes.
