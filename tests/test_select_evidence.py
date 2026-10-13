from answer import select_evidence


def _hit(cid, sec, score):
    return {"chunk_id": cid, "generic_name": "X", "section": sec, "score": score}


def test_each_routed_section_gets_a_slot_in_priority_order():
    hits = [_hit("a:warnings:0", "warnings", 9),
            _hit("b:warnings:1", "warnings", 8),
            _hit("c:contraindications:0", "contraindications", 5)]
    chosen = select_evidence(hits, ["contraindications", "warnings"], limit=2)
    assert [h["section"] for h in chosen] == ["contraindications", "warnings"]