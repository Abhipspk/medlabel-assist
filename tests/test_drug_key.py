from retrieval import drug_key


def test_drug_key_takes_first_meaningful_word():
    assert drug_key("METFORMIN HYDROCHLORIDE") == "metformin"
    assert drug_key("Sodium Fluoride") == "fluoride"