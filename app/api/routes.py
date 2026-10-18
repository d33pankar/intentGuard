"""V1 routes: field extraction, gated scoring into per-product fact tables,
and read-only latest-result queries for the dashboard/UI."""
import logging
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.schemas import (
    CueHitOut,
    DayActivity,
    ExtractResponse,
    FieldStatusOut,
    ModelInfo,
    ProductOut,
    ProductMetrics,
    ResultRow,
    ScoreResponse,
)
from app.core.config import settings
from app.db.database import get_db
from app.db.models import DimProduct, MidRegistry, fact_class_for, latest_view_name
from app.decisions.policy import decide
from app.ingestion.extract import extract_fields, strip_leading_header
from app.ingestion.speakers import customer_text
from app.identity.resolve import (
    IdentityConflictError,
    normalize_email,
    normalize_phone,
    resolve_customer,
)
from app.inference.registry import default_scorer_name, get_scorer_by_name, list_models
from app.ingestion.extract import REQUIRED_FIELDS, extract_fields, missing_fields

log = logging.getLogger(__name__)
router = APIRouter()


async def _read_transcript(file: UploadFile) -> str:
    """Read + validate the raw transcript, preserving line structure (the
    field extractor needs it)."""
    filename = (file.filename or "").lower()
    if not filename.endswith(".txt"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only plain-text .txt transcripts are accepted in V1.",
        )
    raw = await file.read()
    if len(raw) > settings.wts_max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File exceeds {settings.wts_max_upload_bytes} byte limit.",
        )
    try:
        text_content = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be valid UTF-8 plain text.",
        )
    if not text_content.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transcript is empty.",
        )
    if len(text_content) > settings.wts_max_transcript_chars:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transcript exceeds character limit.",
        )
    return text_content


def _catalogue(db: Session) -> list[tuple[str, str]]:
    return [
        (p.product_id, p.product_name)
        for p in db.query(DimProduct).order_by(DimProduct.product_id).all()
    ]


@router.post("/v1/extract", response_model=ExtractResponse)
async def extract_transcript_fields(
    file: UploadFile = File(description="Plain-text (.txt) call transcript"),
    db: Session = Depends(get_db),
) -> ExtractResponse:
    """Best-effort field extraction. Read-only: finds what it can, names what
    it can't. The UI highlights missing fields for the user to complete."""
    raw_text = await _read_transcript(file)
    status = extract_fields(raw_text, _catalogue(db))
    return ExtractResponse(
        fields={
            name: FieldStatusOut(value=s.value, found=s.found)
            for name, s in status.items()
        },
        missing=missing_fields(status),
    )


def _validate_fields(
    db: Session, values: dict[str, str]
) -> tuple[DimProduct, date]:
    """Strict gate: EVERY field must be present and valid, else 400 naming
    the offenders. Scoring cannot proceed otherwise."""
    missing = [f for f in REQUIRED_FIELDS if not (values.get(f) or "").strip()]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Incomplete fields — cannot score. Missing: {', '.join(missing)}.",
        )
    product = db.get(DimProduct, values["product_id"].strip())
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown product_id {values['product_id'].strip()!r}. "
            "Choose one from GET /v1/products.",
        )
    if product.product_name.strip().lower() != values["product_name"].strip().lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"product_name {values['product_name'].strip()!r} does not match "
            f"the catalogue name {product.product_name!r} for {product.product_id}.",
        )
    from app.ingestion.extract import _parse_date

    call_date = _parse_date(values["date_of_call"])
    if call_date is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"date_of_call {values['date_of_call'].strip()!r} is not a "
            "recognizable date (use YYYY-MM-DD).",
        )
    if call_date > date.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="date_of_call is in the future.",
        )
    if normalize_phone(values["customer_phone"]) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="customer_phone is not a valid phone number.",
        )
    if normalize_email(values["customer_email"]) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="customer_email is not a valid email address.",
        )
    return product, call_date


@router.get("/v1/models", response_model=list[ModelInfo])
def list_scoring_models() -> list[ModelInfo]:
    """Scoring-model catalogue for the UI dropdown. Listing never loads
    model weights."""
    return [ModelInfo(**m) for m in list_models()]


@router.post("/v1/score", response_model=ScoreResponse)
async def score_transcript(
    file: UploadFile = File(description="Plain-text (.txt) call transcript"),
    mid: str = Form(default="", description="Known MID (skip identity matching)"),
    model: str = Form(default="", description="Scorer name (see GET /v1/models)"),
    prompt_style: str = Form(
        default="",
        description="Prompt style id; only models advertising prompt_styles",
    ),
    product_id: str = Form(default=""),
    product_name: str = Form(default=""),
    date_of_call: str = Form(default=""),
    customer_name: str = Form(default=""),
    customer_phone: str = Form(default=""),
    customer_email: str = Form(default=""),
    customer_address: str = Form(default=""),
    db: Session = Depends(get_db),
) -> ScoreResponse:
    """Score one transcript. ALL seven fields are mandatory — missing or
    invalid fields return 400 and nothing is recorded."""
    raw_text = await _read_transcript(file)
    conversation = strip_leading_header(raw_text)
    # Score the customer's utterances when turns are labelled — agent
    # positivity ("Excellent! Perfect deal!") must not inflate interest.
    cust = customer_text(conversation)
    scoped = cust if cust.strip() else conversation
    scored_scope = "customer" if cust.strip() else "whole"
    normalized = " ".join(scoped.split())
    if not normalized:
        raise HTTPException(
            status_code=400,
            detail="Transcript has no conversation content outside its header block. "
            "Paste the call dialogue below the '---' line (a header alone cannot be scored).",
        )
    product, call_date = _validate_fields(
        db,
        {
            "product_id": product_id,
            "product_name": product_name,
            "date_of_call": date_of_call,
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "customer_email": customer_email,
            "customer_address": customer_address,
        },
    )
    fact_cls = fact_class_for(product.product_id, db.get_bind())

    # Identity: known MID wins; otherwise match-or-create from the fields.
    mid = (mid or "").strip()
    customer_status = "provided"
    if mid:
        known = db.query(MidRegistry).filter_by(mid=mid).one_or_none() is not None
        if not known:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown MID {mid!r}. Omit MID to resolve by phone/email.",
            )
    else:
        try:
            resolution = resolve_customer(
                db,
                phone=customer_phone,
                email=customer_email,
                full_name=customer_name,
                address=customer_address,
            )
        except IdentityConflictError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"{exc} No score was recorded.",
            )
        mid = resolution.mid
        customer_status = resolution.status

    try:
        scorer = get_scorer_by_name(model or default_scorer_name(),
                                     prompt_style or "")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    try:
        result = scorer.score(normalized)
    except RuntimeError as exc:
        # Model-level failure with a safe message (e.g. weights unavailable).
        log.exception("Inference failed (mid=%s, model=%s)", mid, scorer.model_name)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference failed ({exc}); no decision was recorded.",
        )
    except Exception:  # inference must never leak internals (spec 6)
        log.exception("Inference failed (mid=%s)", mid)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Inference failed; no decision was recorded.",
        )
    log.info(
        "scored chars=%d label=%s score=%.3f mid=%s product=%s status=%s scope=%s",
        len(normalized), result.label, result.interest_score, mid,
        product.product_id, customer_status, scored_scope,
    )
    decision = decide(result)

    # Append-only fact event. Failed uploads raise above, so they can never
    # fabricate history here.
    db.add(
        fact_cls(
            mid=mid,
            label=result.label,
            interest_score=result.interest_score,
            decision_status=decision["decision_status"],
            engine_resolution=decision["engine_resolution"],
            to_stop=decision["to_stop"],
            evidence=result.evidence,
            model_version=result.model_version,
            call_date=call_date,
        )
    )
    db.commit()

    return ScoreResponse(
        mid=mid,
        customer_status=customer_status,
        product_id=product.product_id,
        call_date=call_date.isoformat(),
        label=result.label,
        interest_score=result.interest_score,
        evidence=result.evidence,
        model_version=result.model_version,
        opt_out_detected=result.opt_out_detected,
        persisted=True,
        evidence_verdict=result.evidence_detail.verdict,
        evidence_prompt=list(result.evidence_detail.prompt),
        evidence_cues=[
            CueHitOut(cue=h.cue, speaker=h.speaker, quote=h.quote,
                      strong=h.strong)
            for h in result.evidence_detail.cues
        ],
        evidence_excerpt=result.evidence_detail.excerpt,
        scored_scope=scored_scope,
        prompt_style=getattr(scorer, "prompt_style", ""),
        insufficient_signal=result.insufficient_signal,
        **decision,
    )


@router.get("/v1/products", response_model=list[ProductOut])
def list_products(db: Session = Depends(get_db)) -> list[ProductOut]:
    """Read-only product catalogue for the upload form dropdown."""
    products = db.query(DimProduct).order_by(DimProduct.product_id).all()
    return [ProductOut(product_id=p.product_id, product_name=p.product_name) for p in products]


@router.get("/v1/products/{product_id}/metrics", response_model=ProductMetrics)
def product_metrics(product_id: str, db: Session = Depends(get_db)) -> ProductMetrics:
    """Read-only aggregate performance for one product. Counts reflect the
    latest scoring event per MID; activity reflects raw scoring volume."""
    from datetime import date, timedelta

    product = db.get(DimProduct, product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown product_id {product_id!r}.",
        )
    fact_cls = fact_class_for(product_id, db.get_bind())
    view = latest_view_name(product_id)

    counts = dict(
        db.execute(
            text(
                f"SELECT engine_resolution, COUNT(*) FROM {view} GROUP BY engine_resolution"
            )
        ).all()
    )
    # NULL resolution (needs review) comes back with a None key.
    interested = sum(v for k, v in counts.items() if k == "Interested")
    not_interested = sum(v for k, v in counts.items() if k == "Not interested")
    needs_review = sum(v for k, v in counts.items() if k is None)
    total = interested + not_interested + needs_review

    avg_score = db.execute(text(f"SELECT AVG(interest_score) FROM {view}")).scalar()
    opt_outs = db.execute(
        text(f"SELECT COUNT(*) FROM {view} WHERE evidence LIKE 'Explicit opt-out%'")
    ).scalar()

    scores = [
        r[0] for r in db.execute(text(f"SELECT interest_score FROM {view}")).all()
    ]
    buckets = [0, 0, 0, 0, 0]
    for s in scores:
        buckets[min(int(s * 5), 4)] += 1

    since = date.today() - timedelta(days=13)
    raw_activity = db.execute(
        text(
            f"SELECT DATE(scored_at) AS d, COUNT(*), AVG(interest_score)"
            f" FROM {fact_cls.__tablename__}"
            f" WHERE DATE(scored_at) >= DATE('{since.isoformat()}')"
            f" GROUP BY d ORDER BY d"
        )
    ).all()
    by_day = {str(r[0]): (r[1], r[2]) for r in raw_activity}
    activity = []
    for i in range(14):
        day = (since + timedelta(days=i)).isoformat()
        count, avg = by_day.get(day, (0, None))
        activity.append(DayActivity(date=day, count=count, avg_score=avg))

    return ProductMetrics(
        product_id=product_id,
        product_name=product.product_name,
        total_customers=total,
        interested=interested,
        not_interested=not_interested,
        needs_review=needs_review,
        avg_interest_score=round(float(avg_score), 3) if avg_score is not None else None,
        opt_out_count=int(opt_outs or 0),
        score_buckets=buckets,
        activity=activity,
    )


@router.get("/v1/products/{product_id}/results", response_model=list[ResultRow])
def product_results(product_id: str, db: Session = Depends(get_db)) -> list[ResultRow]:
    """Read-only latest result per MID for a product (via the latest view).
    Never runs inference and never writes."""
    product = db.get(DimProduct, product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown product_id {product_id!r}.",
        )
    fact_class_for(product_id, db.get_bind())  # ensure table + latest view exist
    view = latest_view_name(product_id)
    rows = db.execute(
        text(
            f"SELECT v.mid, c.full_name, v.engine_resolution, v.interest_score,"
            f" v.decision_status, v.scored_at, v.model_version, v.call_date"
            f" FROM {view} AS v JOIN dim_customer AS c ON c.mid = v.mid"
            f" ORDER BY v.scored_at DESC"
        )
    ).all()
    return [
        ResultRow(
            mid=r[0],
            full_name=r[1] or "",
            product_id=product_id,
            product_name=product.product_name,
            engine_resolution=r[2],
            interest_score=r[3],
            decision_status=r[4],
            last_evaluated_at=r[5],
            model_version=r[6],
            call_date=str(r[7]) if r[7] else None,
        )
        for r in rows
    ]
