from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import quote

import requests
from lxml import html


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
)


@dataclass(slots=True)
class BingImageResult:
    image_url: str
    thumbnail_url: str
    source_page: str
    title: str
    desc: str


class BingImageClient:
    def __init__(self, timeout: int = 20) -> None:
        self.timeout = timeout
        self.session = requests.Session()

    def fetch_images(self, keyword: str, limit: int = 8) -> list[dict[str, str]]:
        keyword = (keyword or "").strip()
        if not keyword:
            raise ValueError("keyword is required")

        encoded_keyword = quote(keyword, safe="")
        url = (
            "https://cn.bing.com/images/search"
            f"?q={encoded_keyword}&qft=+filterui:imagesize-large&form=IRFLTR&first=1"
        )
        response = self.session.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=self.timeout,
        )
        response.raise_for_status()
        if not response.text:
            raise RuntimeError("请求 Bing 图片搜索失败")

        document = html.fromstring(response.text)
        nodes = document.xpath("//a[contains(@class,'iusc') and @m]")

        results: list[dict[str, str]] = []
        for node in nodes:
            meta_raw = (node.get("m") or "").strip()
            if not meta_raw:
                continue
            try:
                meta = json.loads(meta_raw)
            except json.JSONDecodeError:
                continue

            image_url = str(meta.get("murl") or "").strip()
            thumbnail_url = str(meta.get("turl") or "").strip()
            source_page = str(meta.get("purl") or "").strip()
            title = str(meta.get("t") or "").strip()
            desc = str(meta.get("desc") or "").strip()
            if not image_url:
                continue

            results.append(
                {
                    "image_url": image_url,
                    "thumbnail_url": thumbnail_url,
                    "source_page": source_page,
                    "title": title,
                    "desc": desc,
                }
            )
            if len(results) >= limit:
                break

        return results


def fetch_bing_images(keyword: str, limit: int = 8) -> list[dict[str, str]]:
    return BingImageClient().fetch_images(keyword=keyword, limit=limit)
