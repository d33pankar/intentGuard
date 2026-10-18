"""Evidence builder tests: cues shown in context, never mid-word dumps."""
from app.inference.signals import bare_response_detected, build_evidence, cue_words

LONG = (
    "Agent: Good morning, may I speak with David Chen? "
    "Customer: This is David speaking. Who is calling, please? "
    "Agent: I am Jessica with American Express Corporate Outreach. "
    "Customer: Yeah, go ahead and please send me the brochure over to my email. "
    "I will review it with our accountant next week, no promises yet."
)
FLAT = " ".join(LONG.split())
VERDICT = "Zero-shot P(interested)=0.97 vs P(disengaged)=0.03"


def test_cue_centered_with_ellipsis_and_speaker() -> None:
    cues = cue_words(LONG)
    assert "send me" in cues
    ev = build_evidence(VERDICT, LONG, cues)
    assert ev.verdict == VERDICT
    assert len(ev.cues) >= 1
    first = ev.cues[0]
    assert first.cue == "send me"
    assert first.speaker == "Customer"  # attributed to who said it
    assert "…" in first.quote  # context window, not the transcript opening
    assert "Good morning, may I speak" not in first.quote  # not greetings
    assert "Good morning, may I speak" not in ev.text()


def test_windows_never_cut_mid_word() -> None:
    ev = build_evidence(VERDICT, LONG, ("accountant",))
    inner = ev.cues[0].quote.strip("…")
    pos = FLAT.find(inner)
    assert pos != -1  # faithful substring of the transcript
    assert pos == 0 or FLAT[pos - 1] == " "  # starts at a word boundary
    end = pos + len(inner)
    assert end == len(FLAT) or FLAT[end] == " "  # ends at one too


def test_no_cues_falls_back_to_head_and_tail() -> None:
    text = ("Agent: Good morning, may I speak with David Chen? "
            "Customer: This is David speaking. Who is calling, please? "
            "Agent: I am Jessica with American Express Corporate Outreach, "
            "following up on your inquiry form. " * 2 +
            "Customer: I will review it with our accountant next week. "
            "Goodbye and take care.")
    assert cue_words(text) == ()
    ev = build_evidence(VERDICT, text, ())
    assert ev.cues == ()
    assert "Good morning" in ev.excerpt  # opening kept…
    assert "take care" in ev.excerpt  # …and the decision-carrying closing
    assert "Good morning" in ev.text() and "take care" in ev.text()


def test_engagement_and_hedging_cues_detected() -> None:
    cues = cue_words("email me the guide, I will look it over, no promises")
    assert {"email me", "look it over", "no promises"} <= set(cues)

def test_short_text_has_no_ellipsis() -> None:
    ev = build_evidence(VERDICT, "Yes, sign me up!", ("sign me up",))
    assert "…" not in ev.cues[0].quote


def test_prompt_included_in_text() -> None:
    ev = build_evidence(VERDICT, LONG, (), prompt=("hyp-a", "hyp-b"))
    assert "hyp-a" in ev.text() and "hyp-b" in ev.text()


def test_bare_response_detection() -> None:
    assert bare_response_detected("Yes.")
    assert bare_response_detected("Nope")
    assert bare_response_detected("Yes, go ahead")  # thin even with a cue
    assert not bare_response_detected("Yes I'm interested")  # I'm -> i, m
    assert not bare_response_detected("Yes, I want to proceed. Send the form.")
    assert not bare_response_detected("No thanks, I am not interested. Bye.")


def test_weak_affirmations_never_get_cards() -> None:
    text = "Agent: Is this a good time? Customer: Yes, it is. How can I help?"
    ev = build_evidence(VERDICT, text, cue_words(text))
    assert len(ev.cues) == 1
    assert ev.cues[0].cue == "yes"
    assert ev.cues[0].strong is False  # availability answer, not intent
    assert "Weak mentions" in ev.text()
    assert "Excerpt:" in ev.text()  # context still shown, honestly framed


def test_substantive_cues_keep_cards() -> None:
    ev = build_evidence(VERDICT, LONG, cue_words(LONG))
    by_cue = {h.cue: h for h in ev.cues}
    assert by_cue["send me"].strong is True
    assert "Weak mentions" not in ev.text()
