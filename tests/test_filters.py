import pytest

from src.pipeline.filters import match_size, parse_size_rule


def test_exact_rule():
    rule = parse_size_rule("1300x250")
    assert match_size(1300, 250, [rule])
    assert not match_size(1299, 250, [rule])


def test_ratio_rule():
    rule = parse_size_rule("ratio=5.2+/-5%")
    assert match_size(520, 100, [rule])
    assert match_size(450, 100, [rule]) is False


def test_range_rule():
    rule = parse_size_rule("w>=1200,h>=200")
    assert match_size(1300, 250, [rule])
    assert not match_size(1100, 250, [rule])


def test_invalid_rule():
    with pytest.raises(ValueError):
        parse_size_rule("abc")
