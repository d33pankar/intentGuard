"""Replaceable inference interface (spec sections 4.2, 9.1).

Every model — baseline or fine-tuned — implements `IntentScorer` so the API
and decision policy never depend on a concrete model class.
"""
from dataclasses import dataclass, field
from typing import Protocol

from app.inference.signals import Evidence


INTERESTED = "INTERESTED"
UNCERTAIN = "UNCERTAIN"
DISENGAGED = "DISENGAGED"


@dataclass(frozen=True)
class ScoreResult:
    """Output of scoring one transcript.

    `interest_score`: 0.0 (lowest interest) .. 1.0 (highest interest).
    It is a *score*, not a calibrated probability (spec section 8.2).
    """

    label: str
    interest_score: float
    evidence: str
    model_version: str
    opt_out_detected: bool = False
    cue_words: tuple[str, ...] = field(default_factory=tuple)
    evidence_detail: Evidence = field(default_factory=Evidence)
    insufficient_signal: bool = False


class IntentScorer(Protocol):
    # Registry identity (shown in the model dropdown).
    model_name: str
    model_label: str
    model_description: str
    model_version: str

    def score(self, text: str) -> ScoreResult:
        """Score one normalized transcript. Must not raise on odd input."""
        ...
