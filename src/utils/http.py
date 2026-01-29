from typing import Dict, Optional
from urllib.parse import urlparse

import requests


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def is_blocked(url: str, blocked_domains: Optional[list]) -> bool:
    if not blocked_domains:
        return False
    netloc = urlparse(url).netloc.lower()
    return any(netloc.endswith(d.lower()) for d in blocked_domains)


def head(url: str, timeout: float, headers: Optional[Dict[str, str]] = None):
    hdrs = dict(DEFAULT_HEADERS)
    if headers:
        hdrs.update(headers)
    return requests.head(url, headers=hdrs, allow_redirects=True, timeout=timeout)


def get(url: str, timeout: float, headers: Optional[Dict[str, str]] = None, stream: bool = False):
    hdrs = dict(DEFAULT_HEADERS)
    if headers:
        hdrs.update(headers)
    return requests.get(url, headers=hdrs, stream=stream, timeout=timeout)
