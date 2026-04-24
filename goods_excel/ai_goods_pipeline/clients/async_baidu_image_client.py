from __future__ import annotations

import asyncio
from urllib.parse import quote, urlparse

from ai_goods_pipeline.constants import IMAGE_URL_EMBED_UNSTABLE_HOSTS

try:
    from playwright.async_api import async_playwright
except Exception:  # pragma: no cover - optional runtime dependency
    async_playwright = None


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
)


class AsyncBaiduImageClient:
    def __init__(self, timeout: int = 20) -> None:
        self.timeout = timeout
        self._playwright = None
        self._browser = None
        self._browser_failed = False
        self._browser_lock = asyncio.Lock()

    async def fetch_images(self, keyword: str, limit: int = 8) -> list[dict[str, str]]:
        keyword = (keyword or "").strip()
        if not keyword:
            raise ValueError("keyword is required")
        url = self._build_search_url(keyword)
        return await self._fetch_images_rendered(url, limit)

    async def close(self) -> None:
        async with self._browser_lock:
            if self._browser is not None:
                try:
                    await asyncio.wait_for(self._browser.close(), timeout=self.timeout)
                except Exception:
                    pass
                self._browser = None
            if self._playwright is not None:
                try:
                    await asyncio.wait_for(self._playwright.stop(), timeout=self.timeout)
                except Exception:
                    pass
                self._playwright = None

    async def can_render(self) -> bool:
        browser = await self._get_browser()
        return browser is not None

    def _build_search_url(self, keyword: str) -> str:
        encoded_keyword = quote(keyword, safe="")
        return (
            "https://image.baidu.com/search/index"
            f"?tn=baiduimage&fm=result&ie=utf-8&word={encoded_keyword}"
        )

    async def _fetch_images_rendered(self, url: str, limit: int) -> list[dict[str, str]]:
        browser = await self._get_browser()
        if browser is None:
            return []

        page = None
        try:
            page = await browser.new_page(
                user_agent=USER_AGENT,
                viewport={"width": 1600, "height": 1200},
                locale="zh-CN",
            )
            await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout * 1000)
            await page.wait_for_selector(
                'a[href*="/search/detail?"][href*="objurl="][href*="tn=baiduimagedetail"]',
                timeout=self.timeout * 1000,
            )
            await page.wait_for_timeout(800)
            await self._expand_search_results(page, limit)
            items = await page.evaluate(
                """
                (maxCount) => {
                  const maxScanCount = Math.max(maxCount * 4, maxCount);
                  const links = Array.from(
                    document.querySelectorAll(
                      'a[href*="/search/detail?"][href*="objurl="][href*="tn=baiduimagedetail"]'
                    )
                  );

                  return links
                    .filter((link) => {
                      const img = link.querySelector('img');
                      if (!img) {
                        return false;
                      }
                      try {
                        const parsed = new URL(link.href);
                        return Boolean(parsed.searchParams.get('objurl'));
                      } catch (error) {
                        return false;
                      }
                    })
                    .slice(0, maxScanCount)
                    .map((link) => {
                      const img = link.querySelector('img');
                      let objurl = '';
                      let fromurl = '';
                      let word = '';
                      let bdtype = '';
                      let pn = '';
                      try {
                        const parsed = new URL(link.href);
                        objurl = decodeURIComponent(parsed.searchParams.get('objurl') || '');
                        fromurl = decodeURIComponent(parsed.searchParams.get('fromurl') || '');
                        word = decodeURIComponent(parsed.searchParams.get('word') || '');
                        bdtype = parsed.searchParams.get('bdtype') || '';
                        pn = parsed.searchParams.get('pn') || '';
                      } catch (error) {
                        objurl = '';
                      }

                      return {
                        image_url: objurl,
                        thumbnail_url:
                          img?.currentSrc ||
                          img?.src ||
                          '',
                        data_imgurl: img?.getAttribute('data-imgurl') || '',
                        source_page: fromurl,
                        title:
                          img?.getAttribute('alt') ||
                          link.getAttribute('title') ||
                          '',
                        desc: word,
                        bdtype,
                        pn,
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
                await page.close()

    async def _expand_search_results(self, page, limit: int) -> None:
        selector = 'a[href*="/search/detail?"][href*="objurl="][href*="tn=baiduimagedetail"]'
        target_count = max(limit * 3, limit)
        previous_count = 0
        stable_rounds = 0
        for _ in range(3):
            current_count = await page.evaluate(
                "(selector) => document.querySelectorAll(selector).length",
                selector,
            )
            if current_count >= target_count:
                break
            await page.mouse.wheel(0, 2200)
            await page.wait_for_timeout(700)
            refreshed_count = await page.evaluate(
                "(selector) => document.querySelectorAll(selector).length",
                selector,
            )
            if refreshed_count <= previous_count:
                stable_rounds += 1
                if stable_rounds >= 2:
                    break
            else:
                stable_rounds = 0
            previous_count = max(previous_count, refreshed_count)

    async def _get_browser(self):
        if async_playwright is None or self._browser_failed:
            return None
        if self._browser is not None:
            return self._browser
        async with self._browser_lock:
            if self._browser is not None:
                return self._browser
            if async_playwright is None or self._browser_failed:
                return None
            try:
                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(headless=True)
                return self._browser
            except Exception:
                self._browser_failed = True
                await self.close()
                return None

    def _dedupe_results(
        self, items: list[dict[str, str]] | None, limit: int
    ) -> list[dict[str, str]]:
        results: list[dict[str, str]] = []
        seen = set()
        for item in items or []:
            image_url = self._select_candidate_image_url(item)
            if not image_url or image_url in seen:
                continue
            seen.add(image_url)
            results.append(
                {
                    "image_url": image_url,
                    "raw_image_url": str(item.get("image_url") or "").strip(),
                    "thumbnail_url": str(item.get("thumbnail_url") or "").strip(),
                    "data_imgurl": str(item.get("data_imgurl") or "").strip(),
                    "source_page": str(item.get("source_page") or "").strip(),
                    "title": str(item.get("title") or "").strip(),
                    "desc": str(item.get("desc") or "").strip(),
                    "bdtype": str(item.get("bdtype") or "").strip(),
                    "resolved_from": self._resolve_from(item, image_url),
                    "pn": str(item.get("pn") or "").strip(),
                }
            )
            if len(results) >= limit:
                break
        return results

    def _resolve_from(self, item: dict[str, str], image_url: str) -> str:
        raw_image_url = str(item.get("image_url") or "").strip()
        data_imgurl = str(item.get("data_imgurl") or "").strip()
        if image_url and image_url == raw_image_url:
            return "objurl"
        if image_url and image_url == data_imgurl:
            return "data-imgurl"
        return "thumbnail"

    def _select_candidate_image_url(self, item: dict[str, str]) -> str:
        return next(iter(self._candidate_image_urls(item)), "")

    def _candidate_image_urls(self, item: dict[str, str]) -> list[str]:
        raw_image_url = str(item.get("image_url") or "").strip()
        thumbnail_url = str(item.get("thumbnail_url") or "").strip()
        data_imgurl = str(item.get("data_imgurl") or "").strip()
        bdtype = str(item.get("bdtype") or "").strip()

        ordered = [raw_image_url, thumbnail_url, data_imgurl]
        if self._should_prefer_thumbnail_url(
            raw_image_url=raw_image_url,
            thumbnail_url=thumbnail_url,
            bdtype=bdtype,
        ):
            ordered = [thumbnail_url, data_imgurl, raw_image_url]

        deduped: list[str] = []
        seen: set[str] = set()
        for url in ordered:
            value = str(url or "").strip()
            if not value or value in seen:
                continue
            deduped.append(value)
            seen.add(value)
        return deduped

    def _should_prefer_thumbnail_url(
        self,
        *,
        raw_image_url: str,
        thumbnail_url: str,
        bdtype: str,
    ) -> bool:
        if not thumbnail_url:
            return False
        if not raw_image_url:
            return True
        if self._is_embed_unstable_url(raw_image_url):
            return True
        if not self._looks_like_direct_image_url(raw_image_url):
            return True
        if bdtype == "14" and not self._looks_like_direct_image_url(raw_image_url):
            return True
        return False

    def _is_embed_unstable_url(self, url: str) -> bool:
        host = (urlparse(url).netloc or "").lower()
        return any(token in host for token in IMAGE_URL_EMBED_UNSTABLE_HOSTS)

    def _looks_like_direct_image_url(self, url: str) -> bool:
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower()
        path = (parsed.path or "").lower()
        full = url.lower()

        if not host:
            return False
        if path.endswith((".html", ".htm", ".php", ".aspx", ".jsp")):
            return False
        if any(path.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".svg")):
            return True
        if "image_search/src=" in full:
            return True
        if "/it/" in path and "f=jpeg" in full:
            return True
        if "/it/" in path and "f=png" in full:
            return True
        if "/it/" in path and "f=webp" in full:
            return True
        if host.endswith(".baidu.com") and ("fmt=auto" in full or "f=jpeg" in full):
            return True
        return False
