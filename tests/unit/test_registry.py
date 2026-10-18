"""Registry tests: every model plugs in through one place."""
import pytest

from app.inference.registry import (
    default_scorer_name,
    get_scorer_by_name,
    list_models,
)


def test_default_is_baseline() -> None:
    assert default_scorer_name() == "baseline"
    assert get_scorer_by_name("").model_name == "baseline"


def test_unknown_model_rejected() -> None:
    with pytest.raises(ValueError, match="Available"):
        get_scorer_by_name("gpt-99")


def test_list_models_has_dropdown_metadata() -> None:
    models = {m["name"]: m for m in list_models()}
    assert set(models) == {"baseline", "hf-zeroshot"}
    for m in models.values():
        assert m["label"] and m["description"] and m["version"]


def test_registry_scorers_share_interface() -> None:
    from app.inference.baseline import TfidfLogRegScorer
    from app.inference.zeroshot import HFZeroShotScorer

    base = get_scorer_by_name("baseline")
    assert isinstance(base, TfidfLogRegScorer)
    hf = get_scorer_by_name("hf-zeroshot")
    assert isinstance(hf, HFZeroShotScorer)
    # Baseline is a singleton; HF returns cheap per-request instances that
    # share the lazily-loaded weights cache (styles must not reload models).
    assert get_scorer_by_name("baseline") is base
    again = get_scorer_by_name("hf-zeroshot")
    assert isinstance(again, HFZeroShotScorer)
    assert again.model_version == hf.model_version


def test_prompt_styles_listed_for_hf_only() -> None:
    from app.inference.registry import prompt_styles_for

    assert prompt_styles_for("baseline") == []
    styles = prompt_styles_for("hf-zeroshot")
    assert {s["id"] for s in styles} == {"direct", "literal", "role"}
    assert all(s["label"] and s["description"] for s in styles)


def test_unknown_style_and_baseline_style_rejected() -> None:
    with pytest.raises(ValueError, match="Available"):
        get_scorer_by_name("hf-zeroshot", "pirate")
    with pytest.raises(ValueError, match="takes no prompt style"):
        get_scorer_by_name("baseline", "direct")


def test_baseline_still_default_scores() -> None:
    r = get_scorer_by_name("baseline").score("Yes, sign me up please!")
    assert r.label == "INTERESTED"
