"""Speaker-turn splitting tests (deterministic, no DB needed)."""
from app.ingestion.speakers import customer_text, split_turns

INLINE = ("Agent: Good morning, may I speak with David? "
          "Customer: This is David speaking. Who is calling? "
          "Agent: I am Jessica with Amex. Do you have a minute? "
          "Customer: Yeah, go ahead and give me the rundown.")

LINES = ("Agent: Hello!\n"
         "How are you today?\n"
         "Customer: I am well.\n"
         "Name: Riya here, thanks for calling.\n"
         "Agent: Excellent, perfect, amazing deal for you!")


def test_inline_turns_split_and_customer_extracted() -> None:
    turns = split_turns(INLINE)
    assert [t.speaker for t in turns] == ["agent", "customer"] * 2
    cust = customer_text(INLINE)
    assert "Who is calling" in cust
    assert "give me the rundown" in cust
    assert "Good morning" not in cust  # agent excluded


def test_line_turns_with_continuations_and_unknown_labels() -> None:
    turns = split_turns(LINES)
    assert [t.speaker for t in turns] == ["agent", "customer", "agent"]
    assert "How are you today" in turns[0].text  # continuation attaches
    # "Name:" is not a speaker label — it must not fork a phantom turn,
    # and it must survive inside the customer turn.
    assert "Name: Riya here" in customer_text(LINES)


def test_no_labels_means_no_customer_text() -> None:
    assert split_turns("Just a plain block of dialogue.") == []
    assert customer_text("Just a plain block of dialogue.") == ""


def test_labels_case_insensitive() -> None:
    text = "AGENT: hi\ncustomer: no thanks, goodbye"
    assert customer_text(text) == "Customer: no thanks, goodbye"
