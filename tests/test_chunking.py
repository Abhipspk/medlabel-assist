from chunking import chunk_text


def test_short_text_is_one_chunk():
    assert chunk_text("One. Two.", max_chars=1000) == ["One. Two."]