from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import quote

import requests
from lxml import html

try:
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover - optional runtime dependency
    sync_playwright = None


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
        self._playwright = None
        self._browser = None
        self._browser_failed = False

    def fetch_images(self, keyword: str, limit: int = 8) -> list[dict[str, str]]:
        keyword = (keyword or "").strip()
        if not keyword:
            raise ValueError("keyword is required")

        url = self._build_search_url(keyword)
        # Bing 静态 HTML 的节点顺序和浏览器首屏可见顺序可能不一致，
        # 主流程要按用户实际看到的首屏顺序取图，所以优先走渲染后的 DOM。
        rendered_results = self._fetch_images_rendered(url, limit)
        if rendered_results:
            return rendered_results

        return self._fetch_images_http(url, limit)

    def close(self) -> None:
        try:
            self.session.close()
        except Exception:
            pass
        self.close_browser()

    def close_browser(self) -> None:
        if self._browser is not None:
            try:
                self._browser.close()
            except Exception:
                pass
            self._browser = None
        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

    def can_render(self) -> bool:
        return self._get_browser() is not None

    def __del__(self) -> None:  # pragma: no cover - cleanup best effort
        self.close()

    def _build_search_url(self, keyword: str) -> str:
        encoded_keyword = quote(keyword, safe="")
        return (
            "https://cn.bing.com/images/search"
            f"?q={encoded_keyword}&qft=+filterui:imagesize-large&form=IRFLTR&first=1"
        )

    def _fetch_images_rendered(self, url: str, limit: int) -> list[dict[str, str]]:
        browser = self._get_browser()
        if browser is None:
            return []

        page = None
        try:
            page = browser.new_page(
                user_agent=USER_AGENT,
                viewport={"width": 1600, "height": 1200},
                locale="zh-CN",
            )
            page.goto(url, wait_until="domcontentloaded", timeout=self.timeout * 1000)
            page.wait_for_selector(".imgpt .img_cont.hoff", timeout=self.timeout * 1000)
            page.wait_for_timeout(800)
            items = page.evaluate(
                """
                (maxCount) => {
                  // `.imgpt` 对应图片卡片容器，`.img_cont.hoff` 对应首屏实际展示的图片区域。
                  // 这里必须按页面渲染后的卡片顺序截取前 N 张，保证主图/详情图和 Bing 首屏一致。
                  const boxes = Array.from(document.querySelectorAll('.imgpt'))
                    .filter((box) => box.querySelector('.img_cont.hoff'));
                  return boxes.slice(0, maxCount).map((box) => {
                    const mNode = box.querySelector('a.iusc[m]');
                    let meta = {};
                    if (mNode) {
                      try {
                        meta = JSON.parse(mNode.getAttribute('m') || '{}');
                      } catch (error) {
                        meta = {};
                      }
                    }

                    const detailLink = box.querySelector('a[href*="view=detailV2"]');
                    let detailMediaUrl = '';
                    if (detailLink) {
                      try {
                        detailMediaUrl =
                          new URL(detailLink.href).searchParams.get('mediaurl') || '';
                      } catch (error) {
                        detailMediaUrl = '';
                      }
                    }

                    const thumbImg = box.querySelector('.img_cont.hoff img');
                    return {
                      image_url: meta.murl || detailMediaUrl || thumbImg?.src || '',
                      thumbnail_url: thumbImg?.src || meta.turl || '',
                      source_page: meta.purl || '',
                      title: meta.t || '',
                      desc: meta.desc || '',
                    };
                  });
                }
                """,
                limit,
            )
            return self._dedupe_results(items, limit)
        except Exception:
            return []
        finally:
            if page is not None:
                page.close()

    def _fetch_images_http(self, url: str, limit: int) -> list[dict[str, str]]:
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

    def _get_browser(self):
        if sync_playwright is None or self._browser_failed:
            return None
        if self._browser is not None:
            return self._browser
        try:
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=True)
            return self._browser
        except Exception:
            self._browser_failed = True
            self.close()
            return None

    def _dedupe_results(
        self, items: list[dict[str, str]] | None, limit: int
    ) -> list[dict[str, str]]:
        results: list[dict[str, str]] = []
        seen = set()
        for item in items or []:
            image_url = str(item.get("image_url") or "").strip()
            if not image_url or image_url in seen:
                continue
            seen.add(image_url)
            results.append(
                {
                    "image_url": image_url,
                    "thumbnail_url": str(item.get("thumbnail_url") or "").strip(),
                    "source_page": str(item.get("source_page") or "").strip(),
                    "title": str(item.get("title") or "").strip(),
                    "desc": str(item.get("desc") or "").strip(),
                }
            )
            if len(results) >= limit:
                break
        return results


def fetch_bing_images(keyword: str, limit: int = 8) -> list[dict[str, str]]:
    return BingImageClient().fetch_images(keyword=keyword, limit=limit)
