"""Decision mapping: model label -> user-facing WTS outcome (spec 2.3, 8.3)."""
from app.core.config import settings
from app.inference.interface import DISENGAGED, INTERESTED, UNCERTAIN, ScoreResult

DECIDED = "DECIDED"
REQUIRES_REVIEW = "REQUIRES_REVIEW"

ENGINE_INTERESTED = "Interested"
ENGINE_NOT_INTERESTED = "Not interested"
# NOTE: `Not contacted` is a contact-history state, never a model output.
# It is produced only in Milestone 2/4 when no qualifying contact exists.


def decide(result: ScoreResult) -> dict:
    """Map a ScoreResult to a WTS decision.

    Uncertain outputs surface as REQUIRES_REVIEW with a null
    engine_resolution — never forced into Interested/Not interested,
    and never labelled `Not contacted` (spec 2.3).
    """
    threshold = settings.wts_threshold
    if result.label == INTERESTED and result.interest_score >= threshold:
        return {
            "decision_status": DECIDED,
            "engine_resolution": ENGINE_INTERESTED,
            "to_stop": False,
        }
    if result.label == DISENGAGED:
        return {
            "decision_status": DECIDED,
            "engine_resolution": ENGINE_NOT_INTERESTED,
            "to_stop": True,
        }
    # UNCERTAIN, or INTERESTED below threshold (contradictory) -> review.
    _ = (UNCERTAIN, threshold)
    return {
        "decision_status": REQUIRES_REVIEW,
        "engine_resolution": None,
        "to_stop": None,
    }
