from routing import route_sections


def test_who_should_not_take_goes_to_contraindications_first():
    assert route_sections("Who should not take metformin?")[0] == "contraindications"


def test_interaction_question_routes_to_interactions():
    assert "drug_interactions" in route_sections("Can warfarin be taken with aspirin?")


def test_unrelated_question_returns_none():
    assert route_sections("What is the capital of France?") is None