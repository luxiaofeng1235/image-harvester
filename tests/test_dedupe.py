from src.pipeline.dedupe import DedupeIndex


def test_dedupe_index():
    d = DedupeIndex()
    assert not d.check_url("http://example.com/a")
    d.add_url("http://example.com/a")
    assert d.check_url("http://example.com/a")

    assert not d.check_hash("abc")
    d.add_hash("abc")
    assert d.check_hash("abc")
