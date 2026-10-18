"""Shared deterministic signals used by every scorer.

The explicit opt-out rule lives here so ALL models (baseline today, HF and
fine-tuned models tomorrow) apply it identically: an explicit do-not-contact
request short-circuits to DISENGAGED with `opt_out_detected=True`, no matter
what the statistical model says (spec section 8.5).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

OPT_OUT_PATTERNS = (
    r"do not (call|contact|email|text|message) me",
    r"don't (call|contact|email|text|message) me",
    r"do not call again",
    r"stop (calling|contacting|emailing|texting|messaging) me",
    r"remove me from .*list",
    r"take me off .*list",
    r"take my number off",
    r"unsubscribe me",
    r"put me on (the |your )?do.?not.?call",
    r"\bdnc\b",
)

INTEREST_CUES = (
    "interested", "sounds good", "sign me up", "schedule", "follow-up",
    "follow up", "call me back", "send me", "send that", "email me",
    "more details", "tell me more", "give me", "go ahead", "look it over",
    "worth a look", "yes", "great", "perfect", "love it", "deal",
)
DISENGAGE_CUES = (
    "not interested", "no thanks", "don't call", "do not call",
    "stop calling", "remove me", "unsubscribe", "not now", "no promises",
    "think about it", "busy", "already have", "switched", "cancel",
    "no need", "waste",
)


def opt_out_detected(text: str) -> bool:
    return any(re.search(p, text.lower()) for p in OPT_OUT_PATTERNS)


# Lone generic affirmations answer *some* question ("is this a good time?"
# → "yes") far more often than they assert intent. They stay detected but
# render as muted footnotes, never cue cards. Every other cue — including
# single words that directly assert intent ("interested", "unsubscribe",
# "busy", "cancel") — keeps full card treatment.
_WEAK_CUES = frozenset({"yes", "great", "perfect", "deal"})


# A bare "yes" / "no" answers *some* question — "are you over 20?", "can you
# hear me?" — not the offer. It must never drive a decision either way.
_BARE_AFFIRM = frozenset(
    {"yes", "yeah", "yep", "yup", "yea", "sure", "ok", "okay", "alright", "fine"}
)
_BARE_NEGATE = frozenset({"no", "nope", "nah", "na"})
_BARE_FILLER = frozenset(
    {"uh", "um", "hmm", "mm", "oh", "ah", "well", "please", "thanks",
     "thank", "you", "hi", "hello", "hey", "bye", "goodbye"}
)
_BARE_TOKENS = _BARE_AFFIRM | _BARE_NEGATE | _BARE_FILLER


def bare_response_detected(text: str) -> bool:
    """True when the text is just a bare yes/no with no substance.

    Strips affirmations, negations and fillers; fewer than three remaining
    words means there is nothing to judge intent from ("Yes.", "Nope",
    "Yes, go ahead"). Anything substantive ("Yes, I want to proceed…",
    "No thanks, not interested") scores normally.
    """
    speech = re.sub(r"^(agent|customer)\s*:\s*", "", text.strip(),
                    flags=re.IGNORECASE)
    words = re.findall(r"[a-z]+", speech.lower())  # splits "i'm" -> i, m
    substance = [w for w in words if w not in _BARE_TOKENS]
    return len(substance) < 3


def cue_words(text: str) -> tuple[str, ...]:
    lowered = text.lower()
    return tuple(cue for cue in INTEREST_CUES + DISENGAGE_CUES if cue in lowered)


_SPEAKER_RE = re.compile(r"(Agent|Customer)\s*:", re.IGNORECASE)


def _word_window(flat: str, idx: int, cue_len: int, radius: int = 80) -> str:
    """`radius` chars of context around a cue, snapped to word boundaries."""
    start = max(0, idx - radius)
    end = min(len(flat), idx + cue_len + radius)
    prefix = "" if start == 0 else "…"
    suffix = "" if end == len(flat) else "…"
    if start > 0:
        space = flat.find(" ", start, idx)
        if space != -1:
            start = space + 1
    if end < len(flat):
        space = flat.rfind(" ", idx + cue_len, end)
        if space != -1 and space > start:
            end = space
    return f"{prefix}{flat[start:end]}{suffix}"


def _speaker_before(flat: str, idx: int, lookback: int = 120) -> str:
    """Nearest `Agent:` / `Customer:` label before the cue, else ''."""
    matches = list(_SPEAKER_RE.finditer(flat, max(0, idx - lookback), idx))
    return matches[-1].group(1).capitalize() + ": " if matches else ""


def _head_tail(flat: str, limit: int = 200) -> str:
    """Opening + closing at word boundaries: closings usually carry the
    decision ("…no promises yet, but it's worth a look. Thanks, bye.")."""
    if len(flat) <= limit:
        return flat
    half = limit // 2
    head, tail_start = flat[:half], len(flat) - half
    space = head.rfind(" ")
    head = head[:space] if space > 0 else head
    space = flat.find(" ", tail_start)
    tail = flat[space + 1:] if space != -1 else flat[tail_start:]
    return f"{head} … {tail}"


@dataclass(frozen=True)
class CueHit:
    """One cue quoted in context: what matched, who said it, where.

    `strong` is False for lone weak words ("yes", "busy") — they answer
    *some* question ("is this a good time?" → "yes") and must never be
    dressed as intent evidence. They render as a muted footnote; only
    substantive phrases get cue cards.
    """

    cue: str
    speaker: str  # "Customer", "Agent", or "" when unknown
    quote: str  # context window; … marks cuts
    strong: bool = True


@dataclass(frozen=True)
class Evidence:
    """Structured grounding for one score.

    `text()` renders the database-safe plain-text form; the API exposes the
    parts so the UI can lay them out (verdict, collapsible prompt, cue
    cards) instead of dumping a paragraph.
    """

    verdict: str = ""
    prompt: tuple[str, ...] = ()
    cues: tuple[CueHit, ...] = ()
    excerpt: str = ""

    def text(self) -> str:
        lines = [self.verdict] if self.verdict else []
        if self.prompt:
            lines.append("Prompt: " + " / ".join(f"{h!r}" for h in self.prompt))
        for hit in self.cues:
            if not hit.strong:
                continue
            who = f"{hit.speaker}: " if hit.speaker else ""
            lines.append(f"{hit.cue!r} — {who}{hit.quote!r}")
        weak = [h.cue for h in self.cues if not h.strong]
        if weak:
            lines.append(f"Weak mentions (not intent evidence): {', '.join(weak)}")
        if self.excerpt and not any(h.strong for h in self.cues):
            lines.append(f"Excerpt: {self.excerpt!r}")
        return "\n".join(lines)


def build_evidence(
    verdict: str,
    text: str,
    cues: tuple[str, ...],
    prompt: tuple[str, ...] = (),
    limit: int = 200,
    max_windows: int = 3,
) -> Evidence:
    """Human-readable grounding: each cue shown *in context*.

    Instead of dumping the transcript opening (which is usually greetings),
    every cue is quoted with ~80 chars of surrounding context, cut at word
    boundaries, attributed to Agent/Customer when labels are present. With
    no cues, an opening+closing excerpt is used — closings usually carry
    the decision.
    """
    flat = " ".join(text.split())
    if not cues:
        return Evidence(
            verdict=verdict, prompt=prompt, excerpt=_head_tail(flat, limit)
        )
    lowered = flat.lower()
    hits = []
    for cue in cues:
        idx = lowered.find(cue)
        if idx == -1:
            continue
        hits.append(
            CueHit(
                cue=cue,
                speaker=_speaker_before(flat, idx).rstrip(": "),
                quote=_word_window(flat, idx, len(cue)),
                strong=cue not in _WEAK_CUES,
            )
        )
        if len(hits) >= max_windows:
            break
    # The opening+closing excerpt always rides along: it is shown whenever
    # no strong cue card carries the context (no cues, or weak words only).
    return Evidence(
        verdict=verdict,
        prompt=prompt,
        cues=tuple(hits),
        excerpt=_head_tail(flat, limit),
    )
