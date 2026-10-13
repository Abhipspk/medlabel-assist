from chunking import chunk_text


def test_short_text_is_one_chunk():
    assert chunk_text("One. Two.", max_chars=1000) == ["One. Two."]


def test_unpunctuated_long_text_respects_max_chars():
    # Test A: 5,000-character run with no punctuation
    text = "x" * 5000
    chunks = chunk_text(text, max_chars=1000)
    assert len(chunks) > 0
    assert all(len(chunk) <= 1000 for chunk in chunks)


def test_empty_string_returns_empty_list():
    # Test B: empty string input
    assert chunk_text("") == []