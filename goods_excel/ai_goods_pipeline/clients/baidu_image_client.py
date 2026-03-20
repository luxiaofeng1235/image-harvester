from __future__ import annotations

from urllib.parse import quote

try:
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover - optional runtime dependency
    sync_playwright = None


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
)


class BaiduImageClient:
    def __init__(self, timeout: int = 20) -> None:
        self.timeout = timeout
        self._playwright = None
        self._browser = None
        self._browser_failed = False

    def fetch_images(self, keyword: str, limit: int = 8) -> list[dict[str, str]]:
        keyword = (keyword or "").strip()
        if not keyword:
            raise ValueError("keyword is required")

        url = self._build_search_url(keyword)
        return self._fetch_images_rendered(url, limit)

    def close(self) -> None:
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

    def __del__(self) -> None:  # pragma: no cover - cleanup best effort
        self.close()

    def _build_search_url(self, keyword: str) -> str:
        encoded_keyword = quote(keyword, safe="")
        return (
            "https://image.baidu.com/search/index"
            f"?tn=baiduimage&fm=result&ie=utf-8&word={encoded_keyword}"
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
            page.wait_for_selector(
                'a[href*="/search/detail?"][href*="objurl="][href*="tn=baiduimagedetail"]',
                timeout=self.timeout * 1000,
            )
            page.wait_for_timeout(800)
            items = page.evaluate(
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
                          img?.getAttribute('data-imgurl') ||
                          '',
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
                page.close()

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
                    "bdtype": str(item.get("bdtype") or "").strip(),
                    "pn": str(item.get("pn") or "").strip(),
                }
            )
            if len(results) >= limit:
                break
        return results


def fetch_baidu_images(keyword: str, limit: int = 8) -> list[dict[str, str]]:
    return BaiduImageClient().fetch_images(keyword=keyword, limit=limit)
