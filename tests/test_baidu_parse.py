import pytest

pytest.importorskip("requests")

from src.sources.baidu import BaiduImageSource


def test_baidu_extract_urls():
    payload = {
        "data": [
            {"replaceUrl": [{"ObjURL": "http://img.example.com/a.jpg"}]},
            {"replaceUrl": [{"ObjURL": "http://img.example.com/b.png"}]},
            {"replaceUrl": [{"ObjURL": "http://img.example.com/c.jpg?src=baidu"}]},
            {},
        ]
    }
    source = BaiduImageSource()
    urls = source._extract_urls(payload)
    assert urls == [
        "http://img.example.com/a.jpg",
        "http://img.example.com/b.png",
    ]
