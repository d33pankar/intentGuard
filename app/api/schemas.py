"""Pydantic schemas for the V1 API (spec section 6)."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ScoreResponse(BaseModel):
    mid: str
    customer_status: str = Field(description="provided | matched | new")
    product_id: str
    call_date: str = Field(description="Date of the call, from the transcript header (YYYY-MM-DD)")
    label: str = Field(description="INTERESTED | UNCERTAIN | DISENGAGED")
    interest_score: float = Field(ge=0.0, le=1.0)
    decision_status: str = Field(description="DECIDED | REQUIRES_REVIEW")
    engine_resolution: Optional[str] = Field(
        default=None,
        description="Interested | Not interested | null (review). "
        "Never 'Not contacted' — that is a contact-history state.",
    )
    to_stop: Optional[bool] = None
    evidence: str
    model_version: str
    opt_out_detected: bool = False
    persisted: bool = True
    # Structured evidence for rich rendering (evidence stays the DB string).
    evidence_verdict: str = ""
    evidence_prompt: list[str] = Field(default_factory=list)
    evidence_cues: list["CueHitOut"] = Field(default_factory=list)
    evidence_excerpt: str = ""
    # Which text the model actually scored: "customer" (labelled turns →
    # agent utterances excluded) or "whole" (no labels found).
    scored_scope: str = "whole"
    # Prompt style used for style-bearing models ("", direct, literal, role).
    prompt_style: str = ""
    # True when the input was too thin to judge (bare yes/no) — the
    # UNCERTAIN is an abstention, not a measurement.
    insufficient_signal: bool = False


class CueHitOut(BaseModel):
    cue: str
    speaker: str = ""
    quote: str = ""
    strong: bool = True


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None


class FieldStatusOut(BaseModel):
    value: Optional[str] = None
    found: bool = False


class ExtractResponse(BaseModel):
    """Best-effort extraction: what the transcript yielded per field, plus
    the missing list the UI highlights for completion."""

    fields: dict[str, FieldStatusOut]
    missing: list[str]


class ModelInfo(BaseModel):
    """One entry for the scoring-model dropdown."""

    name: str
    label: str
    description: str
    version: str
    prompt_styles: list["PromptStyleOut"] = Field(default_factory=list)


class PromptStyleOut(BaseModel):
    id: str
    label: str
    description: str = ""


class ProductOut(BaseModel):
    product_id: str
    product_name: str


class ResultRow(BaseModel):
    """One read-only dashboard row: latest scoring event per MID + product."""

    mid: str
    full_name: str
    product_id: str
    product_name: str
    call_date: Optional[str] = None
    engine_resolution: Optional[str]
    interest_score: Optional[float]
    decision_status: str
    last_evaluated_at: datetime
    model_version: str


class DayActivity(BaseModel):
    date: str
    count: int
    avg_score: Optional[float]


class ProductMetrics(BaseModel):
    """Aggregate performance for one product (latest state per MID)."""

    product_id: str
    product_name: str
    total_customers: int
    interested: int
    not_interested: int
    needs_review: int
    avg_interest_score: Optional[float]
    opt_out_count: int
    score_buckets: list[int] = Field(
        description="5 histogram buckets over [0,0.2),…,[0.8,1.0]"
    )
    activity: list[DayActivity] = Field(description="per-day scoring events, last 14 days")
