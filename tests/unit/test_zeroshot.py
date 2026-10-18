"""HF zero-shot tests with a stubbed pipeline (no weights downloaded)."""
import pytest

from app.decisions.policy import decide
from app.inference.zeroshot import HFZeroShotScorer


def _stub(scores):
    def fake(text, candidate_labels, hypothesis_template):
        assert hypothesis_template == "{}"
        assert len(candidate_labels) == 2
        return {"labels": list(candidate_labels), "scores": list(scores)}

    return fake


def test_interested_maps_through_band() -> None:
    s = HFZeroShotScorer(pipeline_override=_stub([0.82, 0.18]))
    r = s.score("anything at all")
    assert r.label == "INTERESTED"
    assert r.interest_score == pytest.approx(0.82)
    assert r.model_version.startswith("hf-zeroshot-")
    assert decide(r)["engine_resolution"] == "Interested"


def test_mid_band_is_review_not_forced() -> None:
    s = HFZeroShotScorer(pipeline_override=_stub([0.5, 0.5]))
    r = s.score("maybe, not sure")
    assert r.label == "UNCERTAIN"
    d = decide(r)
    assert d["decision_status"] == "REQUIRES_REVIEW"
    assert d["engine_resolution"] is None


def test_opt_out_short_circuits_before_model() -> None:
    def exploding(*a, **k):
        raise AssertionError("model must not be called on opt-out")

    s = HFZeroShotScorer(pipeline_override=exploding)
    r = s.score("Put me on your do not call list.")
    assert r.opt_out_detected is True
    assert r.label == "DISENGAGED"


def test_pipeline_failure_is_runtime_error() -> None:
    def failing(*a, **k):
        raise OSError("CUDA gone")

    s = HFZeroShotScorer(pipeline_override=failing)
    with pytest.raises(RuntimeError, match="HF model inference failed"):
        s.score("hello, please tell me about this offer in detail")

def test_hypotheses_key_on_who_owns_followup() -> None:
    """Guardrail for a real mis-score: the prompt must distinguish
    agent-owned next steps ("email me the brochure") from customer-owned
    brush-offs ("I'll contact you if I decide…"). Vague rewordings that
    drop this distinction regressed a live transcript to DISENGAGED 0.02."""
    seen = {}

    def capture(text, candidate_labels, hypothesis_template):
        seen["labels"] = list(candidate_labels)
        return {"labels": list(candidate_labels), "scores": [0.5, 0.5]}

    HFZeroShotScorer(pipeline_override=capture).score(
        "anything about this offer and its details please")
    interested, disengaged = seen["labels"]
    assert "agent" in interested  # agent-owned follow-up / questions
    assert "themselves" in disengaged  # customer-owned non-commitment


def test_bare_yes_never_reaches_model() -> None:
    def exploding(*a, **k):
        raise AssertionError("model must not be called on bare yes/no")

    s = HFZeroShotScorer(pipeline_override=exploding)
    r = s.score("Yes.")
    assert r.label == "UNCERTAIN"
    assert r.interest_score == 0.5
    assert r.insufficient_signal is True
    assert decide(r)["decision_status"] == "REQUIRES_REVIEW"


def test_literal_style_changes_hypotheses() -> None:
    seen = {}

    def capture(text, candidate_labels, hypothesis_template):
        seen["labels"] = list(candidate_labels)
        return {"labels": list(candidate_labels), "scores": [0.7, 0.3]}

    s = HFZeroShotScorer(pipeline_override=capture, prompt_style="literal")
    r = s.score("Yes, I want to proceed with the offer and sign up today.")
    assert r.label == "INTERESTED"
    assert s.model_version.endswith("-literal")
    assert any("offer itself" in h for h in seen["labels"])
