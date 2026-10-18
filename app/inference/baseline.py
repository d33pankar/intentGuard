"""Baseline 1: TF-IDF + Logistic Regression (spec section 9.1).

Trained deterministically on a small synthetic seed corpus covering the
spec's scenario categories (clear interest, explicit rejection, polite
deflection, uncertainty, mixed intent). This baseline exists to make V1
runnable and to anchor future comparisons — its errors are documented in
the README and it must NOT be presented as production-grade.
"""
from __future__ import annotations

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from app.core.config import settings
from app.inference.interface import DISENGAGED, INTERESTED, ScoreResult, UNCERTAIN
from app.inference.signals import (
    bare_response_detected,
    build_evidence,
    cue_words,
    opt_out_detected,
)

MODEL_VERSION = "baseline-tfidf-lr-v1"
MODEL_NAME = "baseline"
MODEL_LABEL = "Baseline (TF-IDF)"
MODEL_DESCRIPTION = (
    "Fast deterministic TF-IDF + Logistic Regression on 22 synthetic lines. "
    "Best for quick scoring; struggles with polite deflection."
)

# label: 1 = interested, 0 = disengaged.
# Only CLEAR examples train the classifier; the ambiguous/polite-deflection
# examples below are held-out probes expected to land in the review band.
_CLEAR_CORPUS: tuple[tuple[str, int], ...] = (
    ("Yes, I'm interested. Please send me more details about the plan.", 1),
    ("That sounds good, let's schedule a follow-up call next week.", 1),
    ("Great, sign me up. What are the next steps?", 1),
    ("I love it, tell me more about the pricing options.", 1),
    ("Perfect, call me back tomorrow and we can discuss further.", 1),
    ("This looks useful, please send me the brochure and details.", 1),
    ("I'm interested in upgrading, what offers do you have for me?", 1),
    ("Yes please, I'd like to proceed with the application.", 1),
    ("Sounds perfect, let's go ahead with the subscription.", 1),
    ("Thank you, this is exactly what I was looking for.", 1),
    ("Yes, I'm very interested! Please sign me up today.", 1),
    ("Absolutely interested, send me the details right away.", 1),
    ("No thanks, I'm not interested in this product.", 0),
    ("Stop calling me, I already told you I'm not interested.", 0),
    ("Remove me from your list and do not contact me again.", 0),
    ("I already have a provider, please don't call again.", 0),
    ("This is a waste of time, cancel everything and don't call back.", 0),
    ("No need, I switched to another company last month.", 0),
    ("Put me on your do not call list right now.", 0),
    ("Unsubscribe me from all your calls and emails.", 0),
    ("Not interested at all, goodbye.", 0),
    ("No, definitely not interested, please hang up.", 0),
)

# Held-out ambiguous probes (NOT trained on): these should land UNCERTAIN.
_PROBE_CORPUS: tuple[str, ...] = (
    "Thank you for the information. I will contact you if I decide to proceed.",
    "Thanks, but not right now, I'm quite busy these days.",
    "We already have something similar, I'll let you know if anything changes.",
    "I'm not sure this is the right time, maybe later.",
    "Sounds okay but I need to think about it and discuss with family.",
    "Not now please, call me back sometime next quarter.",
    "I might be interested but the price seems too high right now.",
    "Thank you for calling, I'll think it over and get back to you.",
    "I'm happy with my current plan but keep me posted on new offers.",
    "Could you send the details? I'm not promising anything yet.",
    "It's interesting but I'm too busy to decide at the moment.",
    "Maybe later, I need to compare with other options first.",
)

_SEED_CORPUS = _CLEAR_CORPUS  # backwards-compatible alias


class TfidfLogRegScorer:
    """Deterministic TF-IDF + Logistic Regression baseline."""

    model_name = MODEL_NAME
    model_label = MODEL_LABEL
    model_description = MODEL_DESCRIPTION
    model_version = MODEL_VERSION

    def __init__(self) -> None:
        texts = [t for t, _ in _SEED_CORPUS]
        labels = [y for _, y in _SEED_CORPUS]
        self._pipe: Pipeline = Pipeline(
            [
                ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1)),
                # High C: tiny seed corpus must be separable; tuned on the
                # seed only, frozen for all later evaluation (spec 9.3).
                ("clf", LogisticRegression(C=4.0, max_iter=1000, random_state=42)),
            ]
        )
        self._pipe.fit(texts, labels)

    def score(self, text: str) -> ScoreResult:
        normalized = " ".join(text.split())
        proba_interested = float(self._pipe.predict_proba([normalized])[0][1])
        if bare_response_detected(normalized):
            detail = build_evidence(
                "Bare yes/no only — not enough signal to judge intent. "
                "A one-word answer replies to some question, not the offer.",
                normalized, ())
            return ScoreResult(
                label=UNCERTAIN,
                interest_score=0.5,
                evidence=detail.text(),
                model_version=self.model_version,
                opt_out_detected=False,
                cue_words=(),
                evidence_detail=detail,
                insufficient_signal=True,
            )
        opt_out = opt_out_detected(normalized)
        cues = cue_words(normalized)
        low, high = settings.wts_review_band_low, settings.wts_review_band_high
        if opt_out:
            # Documented deterministic rule: explicit opt-out -> DISENGAGED.
            detail = build_evidence(
                "Explicit opt-out request detected.", normalized, cues)
            return ScoreResult(
                label=DISENGAGED,
                interest_score=min(proba_interested, 0.15),
                evidence=detail.text(),
                model_version=self.model_version,
                opt_out_detected=True,
                cue_words=cues,
                evidence_detail=detail,
            )
        if proba_interested >= high:
            label = INTERESTED
        elif proba_interested < low:
            label = DISENGAGED
        else:
            label = UNCERTAIN
        detail = build_evidence(
            f"TF-IDF + Logistic Regression score {proba_interested:.2f}",
            normalized, cues)
        return ScoreResult(
            label=label,
            interest_score=proba_interested,
            evidence=detail.text(),
            model_version=self.model_version,
            opt_out_detected=False,
            cue_words=cues,
            evidence_detail=detail,
        )


# Lazily-built singleton so importing the module stays cheap.
_scorer: TfidfLogRegScorer | None = None


def get_scorer() -> TfidfLogRegScorer:
    global _scorer
    if _scorer is None:
        _scorer = TfidfLogRegScorer()
    return _scorer
