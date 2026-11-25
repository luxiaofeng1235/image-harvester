from __future__ import annotations

from pathlib import Path
from urllib.parse import quote, urlparse

from ai_goods_pipeline.constants import IMAGE_URL_EMBED_UNSTABLE_HOSTS

try:
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover - optional runtime dependency
    sync_playwright = None


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
)


def _find_chrome_path() -> str | None:
    """自动查找可用的 Chrome/Chromium 路径"""
    # 常见 playwright 浏览器目录
    cache_dirs = [
        Path.home() / ".cache" / "ms-playwright",
        Path("/ms-playwright"),  # Linux 全局
    ]
    
    for cache_dir in cache_dirs:
        if not cache_dir.exists():
            continue
        # 查找 chromium-* 目录（按版本号降序）
        chromium_dirs = sorted(
            cache_dir.glob("chromium-*"),
            key=lambda p: p.name,
            reverse=True,
        )
        for chromium_dir in chromium_dirs:
            # 检查常见的 chrome 可执行文件路径
            candidates = [
                chromium_dir / "chrome-linux64" / "chrome",
                chromium_dir / "chrome-linux" / "chrome",
                chromium_dir / "chrome" / "chrome",
            ]
            for chrome_path in candidates:
                if chrome_path.exists():
                    return str(chrome_path)
    
    return None


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
            "https://image.baidu.com/search/index"
            f"?tn=baiduimage&fm=result&ie=utf-8&word={encoded_keyword}"
        )

    def _fetch_images_rendered(self, url: str, limit: int) -> list[dict[str, str]]:
        """
        使用与 fetch_images.py 一致的选择器逻辑：
        直接从 img.main_img.img-hover 的 data-objurl 属性获取原图 URL。
        """
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
            page.goto(url, wait_until="networkidle", timeout=self.timeout * 1000)
            page.wait_for_timeout(2000)
            self._expand_search_results(page, limit)
            items = page.evaluate(
                """
                (maxCount) => {
                  // 优先使用 img.main_img.img-hover 的 data-objurl（原图直链）
                  const imgs = document.querySelectorAll('img.main_img.img-hover');
                  const results = [];
                  
                  imgs.forEach((img, index) => {
                    if (results.length >= maxCount) return;
                    
                    const objUrl = img.getAttribute('data-objurl');
                    if (!objUrl) return;
                    
                    results.push({
                      image_url: objUrl,
                      thumbnail_url: img.currentSrc || img.src || '',
                      data_imgurl: img.getAttribute('data-imgurl') || '',
                      source_page: '',
                      title: img.getAttribute('alt') || '',
                      desc: '',
                      bdtype: '',
                      pn: String(index),
                    });
                  });
                  
                  // 如果没找到 hover 的，取所有带 data-objurl 的 img
                  if (results.length === 0) {
                    document.querySelectorAll('img[data-objurl]').forEach((img, index) => {
                      if (results.length >= maxCount) return;
                      const objUrl = img.getAttribute('data-objurl');
                      if (!objUrl) return;
                      
                      results.push({
                        image_url: objUrl,
                        thumbnail_url: img.currentSrc || img.src || '',
                        data_imgurl: img.getAttribute('data-imgurl') || '',
                        source_page: '',
                        title: img.getAttribute('alt') || '',
                        desc: '',
                        bdtype: '',
                        pn: String(index),
                      });
                    });
                  }
                  
                  return results;
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

    def _expand_search_results(self, page, limit: int) -> None:
        """滚动页面加载更多图片结果，使用与 _fetch_images_rendered 一致的选择器。"""
        selector = 'img.main_img.img-hover[data-objurl]'
        fallback_selector = 'img[data-objurl]'
        target_count = max(limit * 3, limit)
        previous_count = 0
        stable_rounds = 0
        for _ in range(3):
            current_count = page.evaluate(
                "(selector) => document.querySelectorAll(selector).length",
                selector,
            )
            if current_count == 0:
                # 如果没找到 hover 的，用 fallback
                current_count = page.evaluate(
                    "(selector) => document.querySelectorAll(selector).length",
                    fallback_selector,
                )
            if current_count >= target_count:
                break
            page.mouse.wheel(0, 2200)
            page.wait_for_timeout(700)
            refreshed_count = page.evaluate(
                "(selector) => document.querySelectorAll(selector).length",
                selector,
            )
            if refreshed_count == 0:
                refreshed_count = page.evaluate(
                    "(selector) => document.querySelectorAll(selector).length",
                    fallback_selector,
                )
            if refreshed_count <= previous_count:
                stable_rounds += 1
                if stable_rounds >= 2:
                    break
            else:
                stable_rounds = 0
            previous_count = max(previous_count, refreshed_count)

    def _get_browser(self):
        if sync_playwright is None or self._browser_failed:
            return None
        if self._browser is not None:
            return self._browser
        try:
            self._playwright = sync_playwright().start()
            # 自动查找可用的 Chrome 路径
            chrome_path = _find_chrome_path()
            launch_args = {"headless": True, "args": ["--no-sandbox", "--disable-setuid-sandbox"]}
            if chrome_path:
                launch_args["executable_path"] = chrome_path
            self._browser = self._playwright.chromium.launch(**launch_args)
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


def fetch_baidu_images(keyword: str, limit: int = 8) -> list[dict[str, str]]:
    return BaiduImageClient().fetch_images(keyword=keyword, limit=limit)
