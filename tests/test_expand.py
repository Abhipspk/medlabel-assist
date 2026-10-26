from expand import expand_query


def test_poisoned_gets_overdosage_vocabulary():
    assert "overdosage" in expand_query("What if someone is poisoned by metformin?")


def test_unrelated_question_unchanged():
    assert expand_query("What is the capital of France?") == "What is the capital of France?"