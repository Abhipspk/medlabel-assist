from gate import failures, metrics


def row(kind, abstained, **kw):
    base = {"kind": kind, "abstained": abstained, "uncited": False, "section_ok": True,
            "wrong_drug_cited": False, "numbers_ok": True}
    return {**base, **kw}


GOOD = ([row("answerable", False)] * 9 + [row("out_of_scope", True)] * 3 + [row("fictional", True)])


def test_good_results_pass():
    assert failures(metrics(GOOD)) == []


def test_answering_an_out_of_scope_question_fails_the_gate():
    bad = GOOD + [row("out_of_scope", False)]
    assert any("out_of_scope_false_answer_rate" in f for f in failures(metrics(bad)))


def test_citing_the_wrong_drug_fails_the_gate():
    bad = [row("answerable", False, wrong_drug_cited=True)] + GOOD
    assert any("wrong_drug_cited_rate" in f for f in failures(metrics(bad)))


def test_empty_results_fail_closed():
    assert failures(metrics([])) != []