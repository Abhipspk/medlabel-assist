from verify import clean_citations, generate_verified, NO_EVIDENCE


def test_clean_keeps_valid_and_drops_label_section_numbers():
    out = clean_citations("Dose is 150 mg [Excerpt 2.2] and 300 mg [2] or [1.3] [9].", 4)
    assert "[2]" in out and "2.2" not in out and "1.3" not in out and "[9]" not in out


def test_retries_once_then_refuses_when_never_cited():
    calls = []
    def fake_llm(q, ctx):
        calls.append(q)
        return "Some answer with no citation."
    out = generate_verified("q", [{}], fake_llm, lambda e: "ctx")
    assert out == NO_EVIDENCE and len(calls) == 2


def test_retry_can_succeed():
    answers = iter(["no cite", "Fixed answer [1]."])
    out = generate_verified("q", [{}], lambda q, c: next(answers), lambda e: "ctx")
    assert out == "Fixed answer [1]."