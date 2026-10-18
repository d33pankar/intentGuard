"""Hugging Face zero-shot scorer with a custom prompt (spec Baseline 2 path).

Uses an NLI model as a zero-shot intent classifier: the transcript is the
premise and each candidate intent is rendered through a configurable
hypothesis template ("the custom prompt"). The entailment mass on the
INTERESTED hypothesis becomes `interest_score`, mapped through the same
review band as every other scorer.

Default model: MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli (strong
zero-shot, ~350MB, CPU-runnable). Override with HF_MODEL_ID.

Knobs (env):
- HF_MODEL_ID: Hugging Face model id.
- HF_HYPOTHESIS_TEMPLATE: must contain `{label}`, e.g.
  "This customer is {label}."  (default)
- HF_INTERESTED_LABEL: text filling the template for interest
  (default "interested in continuing with the product or service").
- HF_DISENGAGED_LABEL: text filling the template for disengagement.
  The default keys on *who owns the follow-up* — "ending the conversation
  and leaving all follow-up to themselves with no firm commitment" — so
  that customer-owned brush-offs ("I'll contact you if I decide…") score
  disengaged while agent-owned next steps ("email me the brochure")
  score engaged. Tune against a labeled probe set, not single examples.

Cost note: the model downloads on first use and runs in-process on CPU —
fine for a prototype, but a worker/GPU placement belongs to a later stage
(spec warns against loading large models in the API process long-term).

`pipeline_override` exists for tests so they never download weights.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from app.core.config import settings
from app.inference.interface import DISENGAGED, INTERESTED, ScoreResult, UNCERTAIN
from app.inference.signals import (
    bare_response_detected,
    build_evidence,
    cue_words,
    opt_out_detected,
)

log = logging.getLogger(__name__)

MODEL_NAME = "hf-zeroshot"
MODEL_LABEL = "Hugging Face zero-shot (custom prompt)"
MODEL_DESCRIPTION = (
    "NLI zero-shot classification with a configurable hypothesis prompt. "
    "Smarter on polite deflection; slower (downloads ~350MB on first use)."
)


@dataclass(frozen=True)
class PromptStyle:
    """One selectable prompting technique: how intent is phrased to the NLI
    model. Measured on a 5-probe set (polite brush-off, clear yes, soft no,
    brochure request, engaged call) — `direct` 5/5, `literal` 5/5 with
    softer margins, `role` 4/5 (regresses the polite brush-off to
    INTERESTED; shipped for experimentation, not as default)."""

    id: str
    label: str
    description: str
    template: str
    interested: str
    disengaged: str


def prompt_styles() -> dict[str, PromptStyle]:
    """All styles; `direct` tracks the HF_* env knobs, others are fixed."""
    direct = PromptStyle(
        id="direct",
        label="Direct",
        description="Plain hypotheses about who owns the follow-up. "
        "Best measured accuracy.",
        template=settings.hf_hypothesis_template,
        interested=settings.hf_interested_label,
        disengaged=settings.hf_disengaged_label,
    )
    return {
        "direct": direct,
        "literal": PromptStyle(
            id="literal",
            label="Literal commitment",
            description="Strict bar: is the customer committing to the offer "
            "itself? Measured 4/5 — auto-stops engaged-but-hedged "
            "callers (brochure-requester scored 0.39). Compare, don't deploy.",
            template="This customer is {label}.",
            interested=("saying yes to the offer itself by requesting it, "
                        "agreeing to sign up, or confirming a next step"),
            disengaged=("saying no to the offer, putting off the decision, "
                        "or merely answering an unrelated question"),
        ),
        "role": PromptStyle(
            id="role",
            label="Role-framed (experimental)",
            description="Role-based framing ('as an expert analyst…'). "
            "Measured worse on polite brush-offs — compare, don't assume.",
            template=("As an expert sales-conversation analyst, my assessment "
                      "is that this customer is {label}."),
            interested=direct.interested,
            disengaged=direct.disengaged,
        ),
    }


def default_prompt_style() -> str:
    return settings.default_prompt_style or "direct"


# Shared across per-request instances so selecting a style stays cheap —
# weights still load lazily on first real score.
_PIPE_CACHE: dict[str, Any] = {}


class HFZeroShotScorer:
    model_name = MODEL_NAME
    model_label = MODEL_LABEL
    model_description = MODEL_DESCRIPTION

    def __init__(
        self,
        pipeline_override: Callable[..., dict[str, Any]] | None = None,
        prompt_style: str = "",
    ) -> None:
        styles = prompt_styles()
        style_id = (prompt_style or "").strip() or default_prompt_style()
        if style_id not in styles:
            raise ValueError(
                f"Unknown prompt style {prompt_style!r}. "
                f"Available: {', '.join(sorted(styles))}."
            )
        self.prompt_style = style_id
        self._style = styles[style_id]
        self._pipeline_override = pipeline_override
        self._pipe: Any | None = pipeline_override
        self.model_id = settings.hf_model_id
        slug = self.model_id.split("/")[-1]
        self.model_version = f"hf-zeroshot-{slug}-{style_id}"

    @property
    def _pipeline(self) -> Any:
        if self._pipe is None:
            if self.model_id in _PIPE_CACHE:
                self._pipe = _PIPE_CACHE[self.model_id]
            else:
                try:
                    from transformers import pipeline
                except ImportError as exc:
                    raise RuntimeError(
                        "transformers is not installed. Install the 'hf' extra: "
                        "pip install -e \".[hf]\"."
                    ) from exc
                log.info("Loading zero-shot model %s (first use downloads weights)",
                         self.model_id)
                self._pipe = pipeline(
                    "zero-shot-classification",
                    model=self.model_id,
                    device=-1,  # CPU explicitly; GPU placement is a later stage
                )
                _PIPE_CACHE[self.model_id] = self._pipe
        return self._pipe

    def _hypotheses(self) -> tuple[str, str]:
        return (
            self._style.template.format(label=self._style.interested),
            self._style.template.format(label=self._style.disengaged),
        )

    def score(self, text: str) -> ScoreResult:
        normalized = " ".join(text.split())
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
        if opt_out_detected(normalized):
            cues = cue_words(normalized)
            detail = build_evidence(
                "Explicit opt-out request detected.", normalized, cues)
            return ScoreResult(
                label=DISENGAGED,
                interest_score=0.05,
                evidence=detail.text(),
                model_version=self.model_version,
                opt_out_detected=True,
                cue_words=cues,
                evidence_detail=detail,
            )
        hyp_interested, hyp_disengaged = self._hypotheses()
        try:
            # Candidate labels ARE the full custom-prompt hypotheses
            # (template "{}" passes them through untouched).
            out = self._pipeline(
                normalized[:2000],
                candidate_labels=[hyp_interested, hyp_disengaged],
                hypothesis_template="{}",
            )
        except Exception as exc:
            log.exception("HF zero-shot inference failed")
            raise RuntimeError(f"HF model inference failed: {exc}") from exc
        scores = dict(zip(out["labels"], out["scores"]))
        p_interested = float(scores.get(hyp_interested, 0.0))
        p_disengaged = float(scores.get(hyp_disengaged, 0.0))
        low, high = settings.wts_review_band_low, settings.wts_review_band_high
        if p_interested >= high:
            label = INTERESTED
        elif p_interested < low:
            label = DISENGAGED
        else:
            label = UNCERTAIN
        cues = cue_words(normalized)
        detail = build_evidence(
            f"Zero-shot P(interested)={p_interested:.2f} vs "
            f"P(disengaged)={p_disengaged:.2f}",
            normalized,
            cues,
            prompt=(hyp_interested, hyp_disengaged),
        )
        return ScoreResult(
            label=label,
            interest_score=p_interested,
            evidence=detail.text(),
            model_version=self.model_version,
            opt_out_detected=False,
            cue_words=cues,
            evidence_detail=detail,
        )
