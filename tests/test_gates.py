from answer import answer_question


class NoDrug:
    def detect_drug(self, question):
        return None


class WeakEvidence:
    def detect_drug(self, question):
        return "metformin"

    def search_diverse(self, question, drug=None):
        return [{"score": -5.0}]

    def search_by_section(self, question, sections, drug=None):
        return []


def test_unknown_drug_is_refused_before_any_search():
    out = answer_question(NoDrug(), "What is zorvexin used for?")
    assert out["abstained"] and out["reason"] == "no recognized drug"


def test_weak_evidence_is_refused_without_calling_the_llm():
    out = answer_question(WeakEvidence(), "Is metformin better than ibuprofen?")
    assert out["abstained"] and out["reason"] == "low retrieval score"