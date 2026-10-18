"""Speaker-turn splitting so scoring hears the customer, not the agent.

Agent utterances ("Excellent! Perfect! This amazing deal…") are full of
positive words that inflate interest scores. When the transcript labels its
turns (`Agent:` / `Customer:`, case-insensitive; unlabelled continuation
lines attach to the current speaker), scoring runs on the customer's
utterances only. Without recognizable labels the whole conversation is
scored — the caller always reports which scope was used (`scored_scope`).

Must run on text AFTER header stripping: header lines like
`Customer Name: …` would otherwise parse as customer turns.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_AGENT_LABELS = frozenset({"agent", "rep", "sales rep", "representative"})
_CUSTOMER_LABELS = frozenset({"customer", "caller", "client", "prospect"})

# Matches a speaker label ANYWHERE in the text (`Agent: …Customer: …` may
# share one line). Deliberately narrow: generic aliases like "name",
# "phone", "contact" are excluded so dialogue lines starting with them
# never fork phantom turns.
_TURN_RE = re.compile(
    r"\b(agent|rep|representative|customer|caller|client|prospect"
    r"|sales\s+rep)\s*:",
    re.IGNORECASE,
)


def _speaker_of(label: str) -> str | None:
    norm = " ".join(label.strip().lower().split())
    if norm in _AGENT_LABELS:
        return "agent"
    if norm in _CUSTOMER_LABELS:
        return "customer"
    return None


@dataclass(frozen=True)
class Turn:
    speaker: str  # "agent" | "customer"
    text: str


def split_turns(conversation: str) -> list[Turn]:
    """Split dialogue into speaker turns.

    Turns may be line-separated or run inline on one line; unlabelled text
    (continuations, narration, unknown `Name:` prefixes) attaches to the
    current speaker, and text before the first label is prepended to the
    first turn.
    """
    matches = list(_TURN_RE.finditer(conversation))
    if not matches:
        return []
    turns: list[Turn] = []
    preamble = conversation[:matches[0].start()].strip()

    def push(speaker: str, chunk: str) -> None:
        text = " ".join(chunk.split())
        if text:
            turns.append(Turn(speaker=speaker, text=text))

    for i, m in enumerate(matches):
        speaker = _speaker_of(m.group(1))
        assert speaker is not None  # regex only matches known labels
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(conversation)
        chunk = conversation[start:end]
        if i == 0 and preamble:
            chunk = preamble + " " + chunk
        # Merge with previous turn when the same speaker continues.
        if turns and turns[-1].speaker == speaker:
            merged = (turns[-1].text + " " + " ".join(chunk.split())).strip()
            turns[-1] = Turn(speaker=speaker, text=merged)
        else:
            push(speaker, chunk)
    return turns


def customer_text(conversation: str) -> str:
    """Customer utterances joined, or "" when no customer turns exist.

    Turns keep a canonical `Customer:` prefix: it grounds NLI premises,
    and evidence quotes stay attributed after the agent turns are gone.
    (Baseline TF-IDF ignores the out-of-vocabulary token entirely.)
    """
    return "\n".join(f"Customer: {t.text}" for t in split_turns(conversation)
                     if t.speaker == "customer")
