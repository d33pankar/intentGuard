"""Central application settings. Env-overridable; see .env.example."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "IntentGuard"
    # Database: PostgreSQL star schema primary, SQLite automatic fallback.
    database_url: str = ""
    sqlite_fallback_url: str = "sqlite:///./data/intentguard.db"
    # Decision policy (spec sections 2.3, 8.3)
    wts_threshold: float = 0.5
    wts_review_band_low: float = 0.4
    wts_review_band_high: float = 0.6
    # Input limits (spec section 5.3)
    wts_max_transcript_chars: int = 200_000
    wts_max_upload_bytes: int = 204_800  # 200 KiB
    model_version: str = "baseline-tfidf-lr-v1"
    # New transcripts are assumed to belong to this product by default
    default_product_id: str = "product_b"
    # Default scorer for /v1/score ("baseline" | "hf-zeroshot")
    default_model: str = "baseline"
    # Hugging Face zero-shot prompt knobs
    hf_model_id: str = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"
    hf_hypothesis_template: str = "This customer is {label}."
    hf_interested_label: str = (
        "actively moving things forward by asking the agent questions, "
        "requesting materials, or agreeing to a follow-up the agent will perform"
    )
    hf_disengaged_label: str = (
        "ending the conversation and leaving all follow-up to themselves "
        "with no firm commitment"
    )
    # Default selectable prompt style for hf-zeroshot
    # ("direct" | "literal" | "role")
    default_prompt_style: str = "direct"


settings = Settings()
