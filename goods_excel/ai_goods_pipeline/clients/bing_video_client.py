from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import requests
from lxml import html


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
)


@dataclass(slots=True)
class BingVideoCover:
    video: str
    cover_image: str


class BingVideoClient:
    def __init__(self, timeout: int = 20) -> None:
        self.timeout = timeout
        self.session = requests.Session()

    def fetch_video_covers(self, keyword: str, limit: int = 4) -> list[dict[str, str]]:
        keyword = (keyword or "").strip()
        if not keyword:
            raise ValueError("keyword is required")

        query = urlencode({"q": keyword, "form": "HDRSC3"})
        url = f"https://cn.bing.com/videos/search?{query}"
        response = self.session.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=self.timeout,
        )
        response.raise_for_status()
        if not response.text:
            raise RuntimeError("请求必应失败")

        document = html.fromstring(response.text)
        nodes = document.xpath("//div[@ourl]")

        results: list[dict[str, str]] = []
        for node in nodes:
            ourl = (node.get("ourl") or "").strip()
            src_list = node.xpath(".//img[@src]/@src")
            src = src_list[0].strip() if src_list else ""
            if not ourl or not src:
                continue
            results.append({"video": ourl, "cover_image": src})
            if len(results) >= limit:
                break

        return results


def fetch_bing_video_covers(keyword: str, limit: int = 4) -> list[dict[str, str]]:
    """Simple functional wrapper for quick use."""
    return BingVideoClient().fetch_video_covers(keyword=keyword, limit=limit)
