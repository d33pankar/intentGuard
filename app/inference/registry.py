"""Scorer registry: the single place new models plug in.

To add a future model (fine-tuned classifier, LLM judge, …):
1. Implement `IntentScorer` in `app/inference/<name>.py`
   (model_name/model_label/model_description/model_version + score()).
2. Register one line in `_BUILDERS` below.
3. The model dropdown, API validation, and persistence follow automatically.

Construction is always cheap — heavy weights (HF) load lazily on first
`score()` call, never on import or dropdown listing.
"""
from __future__ import annotations

from app.core.config import settings
from app.inference.baseline import MODEL_NAME as BASELINE_NAME, get_scorer
from app.inference.interface import IntentScorer
from app.inference.zeroshot import (
    HFZeroShotScorer,
    MODEL_NAME as HF_NAME,
    prompt_styles,
)

_BUILDERS = {
    BASELINE_NAME: get_scorer,
    HF_NAME: HFZeroShotScorer,
}

_singletons: dict[str, IntentScorer] = {}


def get_scorer_by_name(name: str, prompt_style: str = "") -> IntentScorer:
    name = (name or "").strip() or settings.default_model or BASELINE_NAME
    if name not in _BUILDERS:
        valid = ", ".join(sorted(_BUILDERS))
        raise ValueError(f"Unknown model {name!r}. Available: {valid}.")
    if name == HF_NAME:
        # Style-bearing model: cheap per-request instance sharing the
        # cached weights (still lazy on first real score).
        return HFZeroShotScorer(prompt_style=prompt_style)
    if (prompt_style or "").strip():
        raise ValueError(
            f"Model {name!r} takes no prompt style. "
            f"Available styles: none (prompt styles belong to {HF_NAME})."
        )
    if name not in _singletons:
        _singletons[name] = _BUILDERS[name]()
    return _singletons[name]


def prompt_styles_for(name: str) -> list[dict[str, str]]:
    """Selectable prompt styles for one model (empty when it has none)."""
    if name != HF_NAME:
        return []
    return [
        {"id": s.id, "label": s.label, "description": s.description}
        for s in prompt_styles().values()
    ]


def list_models() -> list[dict[str, object]]:
    """Dropdown metadata for every registered model (never loads weights)."""
    return [
        {
            "name": get_scorer_by_name(name).model_name,
            "label": get_scorer_by_name(name).model_label,
            "description": get_scorer_by_name(name).model_description,
            "version": get_scorer_by_name(name).model_version,
            "prompt_styles": prompt_styles_for(name),
        }
        for name in _BUILDERS
    ]


def default_scorer_name() -> str:
    return settings.default_model or BASELINE_NAME
