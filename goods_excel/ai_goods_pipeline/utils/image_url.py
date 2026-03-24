from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


DIRECT_IMAGE_SUFFIXES = (
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".bmp",
    ".avif",
    ".svg",
)

PROCESSING_QUERY_KEYS = {
    "x-tos-process",
    "x-oss-process",
    "imageview",
    "imageview2",
    "imagemogr2",
    "image_process",
    "x-image-process",
}

SOURCE_IMAGE_QUERY_KEYS = {
    "url",
    "src",
    "imgurl",
    "image_url",
    "mediaurl",
    "origin",
    "target",
    "u",
}

PROXY_TRANSFORM_QUERY_KEYS = {
    "thumbnail",
    "quality",
    "type",
    "format",
    "resize",
    "crop",
    "w",
    "h",
    "width",
    "height",
    "interlace",
    "q",
}

PROCESSING_QUERY_PREFIXES = (
    "x-tos-process=",
    "x-oss-process=",
    "imageview/",
    "imageview2/",
    "imagemogr2/",
)


def normalize_storable_image_url(url: str) -> str:
    text = str(url or "").strip()
    if not text:
        return ""

    parsed = urlsplit(text)
    path = (parsed.path or "").lower()
    query = (parsed.query or "").strip()
    if not query:
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    if not _looks_like_direct_image_path(path):
        return _normalize_proxy_source_query(parsed) or text
    if not _is_processing_query_only(query):
        return text
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def is_standard_storable_image_url(url: str) -> bool:
    text = normalize_storable_image_url(url)
    if not text:
        return False
    parsed = urlsplit(text)
    if _looks_like_direct_image_path((parsed.path or "").lower()):
        return True
    for raw_key, raw_value in parse_qsl(parsed.query or "", keep_blank_values=True):
        key = str(raw_key or "").strip().lower()
        value = str(raw_value or "").strip()
        if key in SOURCE_IMAGE_QUERY_KEYS and _trim_to_image_suffix(value):
            return True
    return False


def _looks_like_direct_image_path(path: str) -> bool:
    return any(path.endswith(ext) for ext in DIRECT_IMAGE_SUFFIXES)


def _is_processing_query_only(query: str) -> bool:
    query_lower = query.lower()
    if query_lower.startswith(PROCESSING_QUERY_PREFIXES):
        return True
    pairs = parse_qsl(query, keep_blank_values=True)
    if not pairs:
        return False
    keys = {str(key or "").strip().lower() for key, _ in pairs if str(key or "").strip()}
    return bool(keys) and keys.issubset(PROCESSING_QUERY_KEYS)


def _normalize_proxy_source_query(parsed) -> str:
    pairs = parse_qsl(parsed.query or "", keep_blank_values=True)
    if not pairs:
        return ""
    normalized_pairs: list[tuple[str, str]] = []
    keys: set[str] = set()
    for raw_key, raw_value in pairs:
        key = str(raw_key or "").strip()
        value = str(raw_value or "").strip()
        key_lower = key.lower()
        if not key or not value:
            continue
        keys.add(key_lower)
        if key_lower not in SOURCE_IMAGE_QUERY_KEYS:
            continue
        trimmed_value = _trim_to_image_suffix(value)
        if not trimmed_value:
            continue
        normalized_pairs.append((key, trimmed_value))

    if not normalized_pairs:
        return ""
    allowed_keys = SOURCE_IMAGE_QUERY_KEYS | PROXY_TRANSFORM_QUERY_KEYS
    if not keys.issubset(allowed_keys):
        return ""
    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urlencode(normalized_pairs),
            "",
        )
    )


def _trim_to_image_suffix(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    lower = text.lower()
    indexes = [
        lower.find(ext)
        for ext in DIRECT_IMAGE_SUFFIXES
        if lower.find(ext) >= 0
    ]
    if not indexes:
        return ""
    end = min(indexes)
    matched_ext = next(
        ext for ext in DIRECT_IMAGE_SUFFIXES if lower.startswith(ext, end)
    )
    return text[: end + len(matched_ext)]
