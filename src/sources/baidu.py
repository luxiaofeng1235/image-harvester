import base64
import hashlib
import json
import logging
import random
import re
import time
from typing import List, Optional, Tuple
from urllib.parse import quote, urlencode

from .base import ImageSource
from ..utils.http import get, is_blocked
from ..utils.rate_limit import RateLimiter
from ..utils.retry import retry


class BaiduImageSource(ImageSource):
    name = "baidu"

    def __init__(self, timeout: float = 10.0, rate_limit: float = 0.5, blocked_domains: Optional[list] = None):
        self.timeout = timeout
        self.limiter = RateLimiter(rate_limit)
        self.blocked_domains = blocked_domains or []
        self.logger = logging.getLogger("image-harvester")
        self._ext_re = re.compile(r"(.*\.(?:jpe?g|png|gif|bmp|webp))", re.I)
        self._user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2_1) AppleWebKit/605.1.15 "
            "(KHTML, like Gecko) Version/17.2 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Edg/120.0.2210.121",
        ]

    def _build_url(self, keyword: str, pn: int, rn: int) -> str:
        params = {
            "tn": "resultjson_com",
            "word": keyword,
            "pn": pn,
            "rn": rn,
            "z": 4,
        }
        return "https://image.baidu.com/search/acjson?" + urlencode(params)

    def _random_referer(self, keyword: str) -> str:
        random_pn = random.randint(0, 100) * 20
        search_pn = random.randint(0, 50) * 10
        base_image = "https://image.baidu.com/"
        base_baidu = "https://www.baidu.com/"
        base_zhidao = "https://zhidao.baidu.com/"
        base_baike = "https://baike.baidu.com/"
        base_tieba = "https://tieba.baidu.com/"
        base_news = "https://news.baidu.com/"
        base_haokan = "https://haokan.baidu.com/"
        base_pan = "https://haokan.baidu.com/"
        base_wenku = "https://haokan.baidu.com/"
        kw = quote(keyword)
        options = [
            base_image,
            f"{base_image}search/index?tn=baiduimage&word={kw}",
            f"{base_image}search/index?tn=baiduimage&word={kw}&pn={random_pn}",
            f"{base_image}search/index?tn=baiduimage&word={kw}&z=0&pn={random_pn}",
            f"{base_image}search/index?tn=baiduimage&word={kw}&z=3&pn={random_pn}",
            f"{base_image}search/index?tn=baiduimage&word={kw}&z=0&pn={random_pn}&rn=30",
            f"{base_image}search/advanced",
            base_baidu,
            f"{base_baidu}s?wd={kw}",
            f"{base_baidu}s?wd={kw}&pn={search_pn}",
            f"{base_zhidao}search?word={kw}",
            f"{base_baike}search?word={kw}",
            f"{base_tieba}f?kw={kw}",
            f"{base_news}ns?word={kw}",
            f"{base_haokan}?sfrom=baidu-top&t={int(time.time())}&r={random.randint(1000,9999)}",
            f"{base_pan}?from={random.randint(1000000,9999999)}h&ts={int(time.time())}",
            f"{base_wenku}?fr=bdpcindex&_wkts_={int(time.time()*1000 + random.randint(100,999))}",
        ]
        return random.choice(options)

    def _random_accept_language(self) -> str:
        return random.choice(
            [
                "zh-CN,zh;q=0.9,en;q=0.8",
                "zh-CN,zh;q=0.9",
                "zh-CN,zh;q=0.9,en;q=0.8,ja;q=0.7",
                "zh-CN,zh-TW;q=0.9,zh;q=0.8,en;q=0.7",
            ]
        )

    def _random_platform(self) -> str:
        return random.choice(['"Windows"', '"macOS"', '"Linux"'])

    def _random_platform_version(self) -> str:
        return random.choice(['"15.0.0"', '"10.0.0"', '"13.3.1"', '"14.2.1"'])

    def _generate_baidu_id(self) -> str:
        return hashlib.md5(str(random.random()).encode("utf-8")).hexdigest().upper()

    def _generate_wise_sids_bfess(self) -> str:
        parts = []
        for _ in range(random.randint(8, 15)):
            parts.append(str(random.randint(100000, 400000)))
        for _ in range(random.randint(35, 50)):
            parts.append(str(random.randint(600000, 630000)))
        for _ in range(random.randint(8, 12)):
            parts.append(str(random.randint(1991000, 1992999)))
        for _ in range(random.randint(5, 10)):
            parts.append(str(random.randint(310000, 620000)))
        for _ in range(random.randint(10, 20)):
            parts.append(str(random.randint(610000, 625000)))
        return "_".join(parts)

    def _generate_ps_ssid(self) -> str:
        return "_".join(str(random.randint(60200, 64700)) for _ in range(random.randint(20, 25)))

    def _generate_zfy_token(self) -> str:
        chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
        token = "".join(random.choice(chars) for _ in range(43))
        return f"{token}:C"

    def _generate_ba_hector(self) -> str:
        return (
            f"{random.randint(100000000, 999999999):x}"
            f"{random.randint(10000000, 99999999):x}"
            f"{random.randint(1000000, 9999999):x}"
            f"{random.randint(100000, 999999):x}"
            f"a{random.randint(100, 999):x}"
            f"a{random.randint(1000000, 9999999):x}"
        )

    def _generate_ab_sr(self) -> str:
        raw = hashlib.sha256(f"{random.random()}{time.time()}".encode("utf-8")).digest()
        return base64.b64encode(raw).decode("ascii")

    def _generate_bduss_bfess(self) -> str:
        raw = hashlib.sha256(f"{random.random()}{time.time()}".encode("utf-8")).hexdigest()[:43]
        return base64.b64encode(raw.encode("ascii")).decode("ascii")

    def _generate_cookie(self) -> str:
        base_time = int(time.time())
        cookies = []
        cookies.append(f"H_WISE_SIDS_BFESS={self._generate_wise_sids_bfess()}")
        if random.randint(0, 1):
            cookies.append(f"MAWEBCUID=web_{hashlib.md5(str(random.random()).encode('utf-8')).hexdigest()[:43]}")
        cookies.append(f"BAIDUID={self._generate_baidu_id()}:FG=1")
        cookies.append(f"PSTM={base_time - random.randint(86400, 2592000)}")
        cookies.append(f"BIDUPSID={hashlib.md5(str(random.random()).encode('utf-8')).hexdigest()[:32].upper()}")
        cookies.append("BDORZ=FFFB88E999055A3F8A630C64834BD6D0")
        if random.randint(0, 1):
            cookies.append("newlogin=1")
        if random.randint(0, 1):
            cookies.append(f"BDUSS_BFESS={self._generate_bduss_bfess()}")
        cookies.append("MCITY=-224%3A")
        cookies.append(f"BAIDUID_BFESS={self._generate_baidu_id()}:FG=1")
        cookies.append(f"ZFY={self._generate_zfy_token()}")
        cookies.append("arialoadData=false")
        cookies.append(f"BA_HECTOR={self._generate_ba_hector()}")
        cookies.append(f"H_PS_PSSID={self._generate_ps_ssid()}")
        cookies.append("BDRCVFR[PWqFiQhMAWs]=9xWipS8B-FspA7EnHc1QhPEUf")
        cookies.append(f"PSINO={random.randint(1, 10)}")
        cookies.append("delPer=0")
        if random.randint(0, 1):
            short_sids = [str(random.randint(60000, 65000)) for _ in range(random.randint(15, 25))]
            cookies.append(f"H_WISE_SIDS={'_'.join(short_sids)}")
        cookies.append(f"ab_sr=1.0.1_{self._generate_ab_sr()}")
        return "; ".join(cookies)

    def _get_headers(self, keyword: str) -> dict:
        ua = random.choice(self._user_agents)
        chrome_version = "120"
        match = re.search(r"Chrome/(\\d+)\\.", ua)
        if match:
            chrome_version = match.group(1)
        sec_ch_ua = f'\"Not_A Brand\";v=\"8\", \"Chromium\";v=\"{chrome_version}\", \"Google Chrome\";v=\"{chrome_version}\"'
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": self._random_accept_language(),
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Host": "image.baidu.com",
            "Referer": self._random_referer(keyword),
            "sec-ch-ua": sec_ch_ua,
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": self._random_platform(),
            "sec-ch-ua-platform-version": self._random_platform_version(),
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "User-Agent": ua,
            "Cookie": self._generate_cookie(),
            "Accept-Encoding": "identity",
        }
        if random.randint(0, 1):
            headers["X-Requested-With"] = "XMLHttpRequest"
        if random.randint(0, 2) == 0:
            headers["Pragma"] = "no-cache"
        if random.randint(0, 1):
            headers["DNT"] = "1"
        return headers

    @retry(attempts=3, backoff=0.5)
    def _fetch_page(self, url: str, keyword: str) -> dict:
        self.limiter.wait()
        headers = self._get_headers(keyword)
        self.logger.debug(
            "baidu_fetch url=%s referer=%s ua=%s",
            url,
            headers.get("Referer"),
            headers.get("User-Agent"),
        )
        resp = get(url, timeout=self.timeout, headers=headers)
        resp.raise_for_status()
        text = resp.text.strip()
        if not text:
            return {}
        # Try to parse JSON even if response contains extra chars
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                return json.loads(text[start:end + 1])
            raise

    def _extract_urls(self, payload: dict) -> List[str]:
        urls: List[str] = []
        data = payload.get("data") or []
        for item in data:
            if not isinstance(item, dict):
                continue
            replace = item.get("replaceUrl")
            if not replace or not isinstance(replace, list):
                continue
            obj = replace[0].get("ObjURL") if replace and isinstance(replace[0], dict) else ""
            if not obj or "src=" in obj:
                continue
            match = self._ext_re.match(obj)
            if not match:
                continue
            url = match.group(1)
            if is_blocked(url, self.blocked_domains):
                continue
            urls.append(url)
        return urls

    def _is_valid_image_header(self, body: bytes) -> bool:
        if len(body) < 8:
            return False
        header = body[:12]
        if header.startswith(b"\xFF\xD8\xFF"):  # JPEG
            return True
        if header.startswith(b"\x89PNG"):  # PNG
            return True
        if header.startswith(b"GIF87a") or header.startswith(b"GIF89a"):
            return True
        if header.startswith(b"RIFF") and header[8:12] == b"WEBP":
            return True
        if header.startswith(b"BM"):
            return True
        if header.startswith(b"II*\x00") or header.startswith(b"MM\x00*"):
            return True
        if header.startswith(b"\x00\x00\x01\x00"):
            return True
        if header.startswith(b"<?xml") and b"<svg" in body.lower():
            return True
        if header.startswith(b"<svg"):
            return True
        return False

    def _check_image_status_batch(self, urls: List[str]) -> List[dict]:
        if not urls:
            return []

        results: List[Optional[dict]] = [None] * len(urls)

        def _probe(url: str) -> Tuple[str, int, bool]:
            ua = random.choice(self._user_agents)
            headers = {
                "User-Agent": ua,
                "Range": "bytes=0-2047",
                "Accept": "image/*,*/*;q=0.8",
            }
            try:
                resp = get(url, timeout=3, headers=headers)
                status = resp.status_code
                content_type = resp.headers.get("Content-Type", "")
                body = resp.content or b""
            except Exception:
                return url, 0, False

            body_stripped = body.lstrip()
            body_text = body_stripped[:2048].decode("utf-8", errors="ignore")
            has_error = re.search(
                r"403 Forbidden|404 Not Found|Error 404|Access Denied|抱歉|禁止访问|error|denied|防盗链|hotlink|页面不存在|找不到文件",
                body_text,
                re.I,
            )
            is_json = re.match(r"^\s*\{.*\}\s*$", body_text, re.S)
            is_html = re.match(r"^\s*<(?:!DOCTYPE|html|body)", body_text, re.I)

            ok = (
                200 <= status < 300
                and content_type.startswith("image/")
                and len(body) > 200
                and not has_error
                and not is_json
                and not is_html
                and self._is_valid_image_header(body_stripped)
            )
            return url, status, ok

        from concurrent.futures import ThreadPoolExecutor, as_completed

        with ThreadPoolExecutor(max_workers=min(16, len(urls))) as pool:
            future_map = {pool.submit(_probe, u): i for i, u in enumerate(urls)}
            for future in as_completed(future_map):
                idx = future_map[future]
                url, status, ok = future.result()
                self.logger.debug("baidu_precheck url=%s status=%s ok=%s", url, status, ok)
                results[idx] = {"url": url, "httpCode": status, "status": ok}

        return [r for r in results if r is not None]

    def _process_image_urls(self, candidate_urls: List[str], show_size: int) -> List[str]:
        try:
            if not candidate_urls:
                return []

            valid_urls: List[str] = []
            idx = 0
            total = len(candidate_urls)

            while idx < total and len(valid_urls) < show_size:
                remaining = total - idx
                needed = show_size - len(valid_urls)
                # First round
                if remaining <= needed:
                    first_round = remaining
                else:
                    first_round = int(needed * 1.5)
                    first_round = max(first_round, 4)
                    first_round = min(first_round, 8)
                    first_round = min(first_round, remaining)

                check_urls = candidate_urls[idx : idx + first_round]
                idx += first_round
                if first_round > 0:
                    check_results = self._check_image_status_batch(check_urls)
                    for res in check_results:
                        if res.get("status") is True:
                            valid_urls.append(res["url"])
                            if len(valid_urls) >= show_size:
                                break

                if len(valid_urls) >= show_size or idx >= total:
                    continue

                # Second round
                remaining_urls = candidate_urls[idx:]
                max_second = min(len(remaining_urls), 6)
                second_round = min(max_second, max(needed * 2, 4))

                if second_round > 0:
                    additional_urls = remaining_urls[:second_round]
                    idx += second_round
                    additional_results = self._check_image_status_batch(additional_urls)
                    for res in additional_results:
                        if res.get("status") is True:
                            valid_urls.append(res["url"])
                            if len(valid_urls) >= show_size:
                                break

            return valid_urls[:show_size]
        except Exception:
            return []

    def fetch_urls(self, keyword: str, limit: int) -> List[str]:
        candidate_urls: List[str] = []
        pn = 0
        rn = min(30, max(10, limit))
        max_pages = max(1, (limit + rn - 1) // rn)

        for page in range(max_pages):
            url = self._build_url(keyword, pn, rn)
            payload = self._fetch_page(url, keyword)
            if isinstance(payload, dict) and payload.get("antiFlag") == 1:
                message = payload.get("message", "antiFlag")
                raise RuntimeError(f"baidu_anti_flag:{message}")
            page_urls = self._extract_urls(payload)
            if not page_urls and page == 0:
                payload = self._fetch_page(url, keyword)
                page_urls = self._extract_urls(payload)
            if not page_urls:
                break
            candidate_urls.extend(page_urls)
            pn += rn
            if len(candidate_urls) >= limit:
                break

        if not candidate_urls:
            # retry once like PHP
            url = self._build_url(keyword, 0, rn)
            payload = self._fetch_page(url, keyword)
            candidate_urls = self._extract_urls(payload)

        # de-dup within source
        seen = set()
        deduped = []
        for u in candidate_urls:
            if u not in seen:
                seen.add(u)
                deduped.append(u)

        # process with two-round validation
        return self._process_image_urls(deduped, limit)
