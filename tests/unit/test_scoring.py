"""Unit tests: baseline scorer + decision mapping (spec 8, Milestone 1)."""
from app.decisions.policy import decide
from app.inference.baseline import TfidfLogRegScorer
from app.inference.interface import DISENGAGED, INTERESTED


def test_interested_transcript_scores_high() -> None:
    scorer = TfidfLogRegScorer()
    result = scorer.score("Yes, I'm very interested! Please sign me up today.")
    assert result.label == INTERESTED
    assert result.interest_score >= 0.6
    decision = decide(result)
    assert decision["engine_resolution"] == "Interested"
    assert decision["to_stop"] is False
    assert decision["decision_status"] == "DECIDED"


def test_disengaged_transcript_scores_low() -> None:
    scorer = TfidfLogRegScorer()
    result = scorer.score("No thanks, I'm not interested. Stop calling me.")
    assert result.label == DISENGAGED
    decision = decide(result)
    assert decision["engine_resolution"] == "Not interested"
    assert decision["to_stop"] is True


def test_explicit_opt_out_is_deterministic_rule() -> None:
    scorer = TfidfLogRegScorer()
    result = scorer.score("Please put me on your do not call list.")
    assert result.opt_out_detected is True
    assert result.label == DISENGAGED


def test_bare_yes_abstains_to_review() -> None:
    scorer = TfidfLogRegScorer()
    result = scorer.score("Yes.")
    assert result.label == "UNCERTAIN"
    assert result.interest_score == 0.5
    assert result.insufficient_signal is True
    decision = decide(result)
    assert decision["decision_status"] == "REQUIRES_REVIEW"
    assert decision["engine_resolution"] is None


def test_polite_deflection_is_not_forced_to_contacted_states() -> None:
    """Polite deflection must surface review/uncertainty honestly, and the
    engine_resolution must never be the contact-history state."""
    from app.inference.interface import ScoreResult

    uncertain = ScoreResult(
        label="UNCERTAIN",
        interest_score=0.5,
        evidence="test",
        model_version="test",
    )
    decision = decide(uncertain)
    assert decision["decision_status"] == "REQUIRES_REVIEW"
    assert decision["engine_resolution"] is None
    assert decision["engine_resolution"] != "Not contacted"
    assert decision["to_stop"] is None


def test_clear_corpus_fully_separated() -> None:
    """All unambiguous seed examples must classify correctly (frozen check)."""
    from app.inference.baseline import _CLEAR_CORPUS

    scorer = TfidfLogRegScorer()
    for text, expected in _CLEAR_CORPUS:
        result = scorer.score(text)
        want = INTERESTED if expected == 1 else DISENGAGED
        assert result.label == want, (text, result)


def test_ambiguous_probes_never_claim_not_contacted() -> None:
    """Known limitation (see README): polite deflection often scores
    INTERESTED — a false-continue, never a 'Not contacted' claim, and
    always with input-grounded evidence. This test locks in that contract
    while H1 (fine-tuned improvement) remains future work."""
    from app.inference.baseline import _PROBE_CORPUS

    scorer = TfidfLogRegScorer()
    for text in _PROBE_CORPUS:
        result = scorer.score(text)
        assert 0.0 <= result.interest_score <= 1.0
        assert result.evidence  # grounded, non-empty
        decision = decide(result)
        assert decision["engine_resolution"] != "Not contacted"
