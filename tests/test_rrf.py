from retrieval import rrf


def test_item_ranked_first_in_both_lists_wins():
    assert rrf([[1, 2, 3], [1, 3, 2]])[0] == 1


def test_item_missing_from_one_list_still_appears():
    assert set(rrf([[1, 2], [3]])) == {1, 2, 3}