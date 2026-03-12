#!/usr/bin/env python3
"""
Batch-clean suspicious question-mark artifacts in existing WordPress posts.

Default mode is dry-run:
  - fetch posts under the configured category tree
  - detect likely corrupted "? / ?? / ???" text fragments in post content
  - write a local JSON report

Apply mode:
  - fetch each target post with `context=edit`
  - clean text nodes only
  - update the existing post content via `POST /wp/v2/posts/{id}`
  - store before/after HTML backups locally
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import requests


WP_API_BASE = "https://www.zgzonre.com/wp-json/wp/v2"
TARGET_CATEGORY_IDS = [37, 38, 39, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 67]
TARGET_PARENT_CATEGORY_IDS = {37, 38, 39}
DEFAULT_TIMEOUT = 30
DEFAULT_SLEEP_SECONDS = 0.4
SPACE_CLASS = r"\s\u00a0\u3000\ufeff"
QUESTION_CLASS = r"\?\uFF1F"
TEXT_FOLLOW_CLASS = r"\u4e00-\u9fffA-Za-z0-9\(（\[【<"
TEXT_PREV_CLASS = r"\u4e00-\u9fffA-Za-z0-9\)）\]】>"
PUNCT_PREV_CLASS = r"：:，,。；;、!！\n\r"

LEADING_ARTIFACT_RE = re.compile(
    rf"(^|[\n\r])([{SPACE_CLASS}]*(?:[{QUESTION_CLASS}][{SPACE_CLASS}]*){{1,5}})(?=[{TEXT_FOLLOW_CLASS}])"
)
AFTER_PUNCT_ARTIFACT_RE = re.compile(
    rf"(?<=[{PUNCT_PREV_CLASS}])(?:[{SPACE_CLASS}]*(?:[{QUESTION_CLASS}][{SPACE_CLASS}]*){{1,5}})(?=[{TEXT_FOLLOW_CLASS}])"
)
INLINE_ARTIFACT_RE = re.compile(
    rf"(?<=[{TEXT_PREV_CLASS}])(?:[{SPACE_CLASS}]*(?:[{QUESTION_CLASS}][{SPACE_CLASS}]*){{1,5}})(?=[{TEXT_FOLLOW_CLASS}])"
)
SPACE_QUESTION_SPACE_RE = re.compile(
    rf"([{SPACE_CLASS}])(?:[{QUESTION_CLASS}][{SPACE_CLASS}]*){{1,5}}(?=[\u4e00-\u9fffA-Za-z0-9])"
)
QUESTION_ONLY_RE = re.compile(rf"^[{SPACE_CLASS}]*(?:[{QUESTION_CLASS}][{SPACE_CLASS}]*)+$")
TRAILING_ARTIFACT_RE = re.compile(
    rf"(?<=[\u4e00-\u9fffA-Za-z0-9\)）\]】。；;!！])(?:[{SPACE_CLASS}]*[{QUESTION_CLASS}])+[{SPACE_CLASS}]*$"
)
WIDE_SPACE_RE = re.compile(r"[ \t]{2,}")
REPORT_FILE = Path("out/question_mark_clean_report.json")
BACKUP_DIR = Path("out/question_mark_clean_backup")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Dry-run or apply a cleanup of corrupted '?/??/???' fragments in existing WP posts."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually update existing WordPress posts. Default is dry-run only.",
    )
    parser.add_argument(
        "--ids",
        type=str,
        help="Comma-separated post IDs to limit updates to a subset.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Only process the first N matched posts.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=DEFAULT_SLEEP_SECONDS,
        help="Seconds to sleep between write requests in apply mode.",
    )
    parser.add_argument(
        "--user",
        type=str,
        default=os.environ.get("WP_USER", "").strip(),
        help="WordPress username. Falls back to WP_USER env var.",
    )
    parser.add_argument(
        "--app-password",
        type=str,
        default=os.environ.get("WP_APP_PASSWORD", "").strip(),
        help="WordPress application password. Falls back to WP_APP_PASSWORD env var.",
    )
    return parser.parse_args()


def build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": "wp-question-cleaner/1.0"})
    return session


def request_json(
    session: requests.Session,
    url: str,
    *,
    params: Optional[Dict[str, object]] = None,
    auth: Optional[Tuple[str, str]] = None,
) -> Tuple[object, requests.Response]:
    response = session.get(url, params=params, auth=auth, timeout=DEFAULT_TIMEOUT)
    response.raise_for_status()
    return response.json(), response


def fetch_target_posts(session: requests.Session) -> List[Dict[str, object]]:
    posts: List[Dict[str, object]] = []
    page = 1

    while True:
        payload, response = request_json(
            session,
            f"{WP_API_BASE}/posts",
            params={
                "categories": ",".join(str(item) for item in TARGET_CATEGORY_IDS),
                "per_page": 100,
                "page": page,
                "_fields": "id,title,categories,content,date",
            },
        )
        page_items = payload if isinstance(payload, list) else []
        posts.extend(page_items)

        total_pages = int(response.headers.get("X-WP-TotalPages", "1"))
        if page >= total_pages:
            break
        page += 1

    return posts


def parse_ids(raw_ids: Optional[str]) -> Optional[set[int]]:
    if not raw_ids:
        return None
    values: set[int] = set()
    for chunk in raw_ids.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        values.add(int(chunk))
    return values


def derive_top_category_name(categories: Sequence[int]) -> str:
    top_map = {
        37: "加热器系列产品",
        38: "搅拌设备系列产品",
        39: "水处理系列产品",
    }
    child_to_top = {
        42: 37,
        43: 37,
        44: 37,
        45: 37,
        46: 37,
        47: 38,
        48: 38,
        49: 39,
        50: 39,
        51: 39,
        67: 39,
    }
    top_ids = []
    for category_id in categories:
        if category_id in TARGET_PARENT_CATEGORY_IDS:
            top_ids.append(category_id)
            continue
        top_id = child_to_top.get(category_id)
        if top_id:
            top_ids.append(top_id)
    deduped = []
    for item in top_ids:
        if item not in deduped:
            deduped.append(item)
    return "、".join(top_map[item] for item in deduped) or "-"


def normalize_spaces(text: str) -> str:
    lines = text.splitlines(keepends=True)
    cleaned_lines = []
    for line in lines:
        if line.strip():
            cleaned_lines.append(WIDE_SPACE_RE.sub(" ", line))
        else:
            cleaned_lines.append(line)
    return "".join(cleaned_lines)


def clean_text_segment(text: str) -> str:
    if QUESTION_ONLY_RE.match(text):
        return ""

    cleaned = text
    cleaned = LEADING_ARTIFACT_RE.sub(r"\1", cleaned)
    cleaned = AFTER_PUNCT_ARTIFACT_RE.sub("", cleaned)
    cleaned = INLINE_ARTIFACT_RE.sub(" ", cleaned)
    cleaned = SPACE_QUESTION_SPACE_RE.sub(r"\1", cleaned)
    cleaned = TRAILING_ARTIFACT_RE.sub("", cleaned)
    cleaned = normalize_spaces(cleaned)
    return cleaned


def collect_match_snippets(text: str, *, limit: int = 6) -> List[str]:
    stripped = re.sub(r"<[^>]*>", " ", text)
    stripped = re.sub(r"https?://\S+", " ", stripped)
    matches = re.finditer(r".{0,24}(?:\?{1,3}|\uFF1F{1,3}).{0,24}", stripped)
    snippets = []
    for match in matches:
        snippet = re.sub(r"\s+", " ", match.group(0)).strip()
        if snippet and snippet not in snippets:
            snippets.append(snippet)
        if len(snippets) >= limit:
            break
    return snippets


class TextNodeCleaner(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.parts: List[str] = []
        self.changed_segments = 0
        self._raw_stack: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        self.parts.append(self.get_starttag_text())
        if tag.lower() in {"script", "style"}:
            self._raw_stack.append(tag.lower())

    def handle_startendtag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        self.parts.append(self.get_starttag_text())

    def handle_endtag(self, tag: str) -> None:
        self.parts.append(f"</{tag}>")
        if self._raw_stack and self._raw_stack[-1] == tag.lower():
            self._raw_stack.pop()

    def handle_data(self, data: str) -> None:
        if self._raw_stack:
            self.parts.append(data)
            return
        cleaned = clean_text_segment(data)
        if cleaned != data:
            self.changed_segments += 1
        self.parts.append(cleaned)

    def handle_entityref(self, name: str) -> None:
        self.parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self.parts.append(f"&#{name};")

    def handle_comment(self, data: str) -> None:
        self.parts.append(f"<!--{data}-->")

    def handle_decl(self, decl: str) -> None:
        self.parts.append(f"<!{decl}>")

    def handle_pi(self, data: str) -> None:
        self.parts.append(f"<?{data}>")

    def unknown_decl(self, data: str) -> None:
        self.parts.append(f"<![{data}]>")

    def get_output(self) -> str:
        return "".join(self.parts)


def clean_html(html: str) -> Tuple[str, int]:
    parser = TextNodeCleaner()
    parser.feed(html)
    parser.close()
    return parser.get_output(), parser.changed_segments


def title_text(post: Dict[str, object]) -> str:
    title = post.get("title") or {}
    if isinstance(title, dict):
        return str(title.get("rendered") or title.get("raw") or "").strip()
    return ""


def rendered_content(post: Dict[str, object]) -> str:
    content = post.get("content") or {}
    if isinstance(content, dict):
        return str(content.get("rendered") or "").strip()
    return ""


def raw_content(post: Dict[str, object]) -> str:
    content = post.get("content") or {}
    if isinstance(content, dict):
        return str(content.get("raw") or "").strip()
    return ""


def build_report(posts: Iterable[Dict[str, object]]) -> List[Dict[str, object]]:
    report: List[Dict[str, object]] = []
    for post in posts:
        original_html = rendered_content(post)
        cleaned_html, changed_segments = clean_html(original_html)
        if cleaned_html == original_html:
            continue
        categories = [int(item) for item in post.get("categories") or []]
        report.append(
            {
                "id": int(post["id"]),
                "title": title_text(post),
                "top_category": derive_top_category_name(categories),
                "categories": categories,
                "changed_segments": changed_segments,
                "snippets": collect_match_snippets(original_html),
            }
        )
    return report


def write_report(report: Sequence[Dict[str, object]]) -> None:
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def require_auth(args: argparse.Namespace) -> Tuple[str, str]:
    if not args.user or not args.app_password:
        raise SystemExit(
            "apply mode requires --user/--app-password or WP_USER/WP_APP_PASSWORD env vars."
        )
    return args.user, args.app_password


def fetch_post_for_edit(
    session: requests.Session,
    post_id: int,
    auth: Tuple[str, str],
) -> Dict[str, object]:
    payload, _response = request_json(
        session,
        f"{WP_API_BASE}/posts/{post_id}",
        params={"context": "edit"},
        auth=auth,
    )
    if not isinstance(payload, dict):
        raise RuntimeError(f"Unexpected response for post {post_id}")
    return payload


def update_post_content(
    session: requests.Session,
    post_id: int,
    cleaned_content: str,
    auth: Tuple[str, str],
) -> requests.Response:
    response = session.post(
        f"{WP_API_BASE}/posts/{post_id}",
        auth=auth,
        json={"content": cleaned_content},
        timeout=DEFAULT_TIMEOUT,
    )
    response.raise_for_status()
    return response


def save_backup(post_id: int, title: str, before_html: str, after_html: str) -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    meta = {"id": post_id, "title": title}
    (BACKUP_DIR / f"{post_id}.meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (BACKUP_DIR / f"{post_id}.before.html").write_text(before_html, encoding="utf-8")
    (BACKUP_DIR / f"{post_id}.after.html").write_text(after_html, encoding="utf-8")


def apply_updates(
    session: requests.Session,
    report: Sequence[Dict[str, object]],
    args: argparse.Namespace,
) -> None:
    auth = require_auth(args)
    for index, item in enumerate(report, start=1):
        post_id = int(item["id"])
        post = fetch_post_for_edit(session, post_id, auth)
        original_html = raw_content(post)
        if not original_html:
            print(f"[skip] {post_id} raw content is empty", file=sys.stderr)
            continue

        cleaned_html, changed_segments = clean_html(original_html)
        if cleaned_html == original_html:
            print(f"[skip] {post_id} no changes after raw-content cleanup")
            continue

        save_backup(post_id, title_text(post), original_html, cleaned_html)
        update_post_content(session, post_id, cleaned_html, auth)
        print(
            f"[updated] {index}/{len(report)} post_id={post_id} changed_segments={changed_segments} title={title_text(post)}"
        )
        if args.sleep > 0:
            time.sleep(args.sleep)


def main() -> None:
    args = parse_args()
    id_filter = parse_ids(args.ids)
    session = build_session()
    posts = fetch_target_posts(session)

    if id_filter:
        posts = [post for post in posts if int(post["id"]) in id_filter]

    report = build_report(posts)
    report.sort(key=lambda item: int(item["id"]), reverse=True)

    if args.limit > 0:
        report = report[: args.limit]

    write_report(report)

    print(f"Target posts fetched: {len(posts)}")
    print(f"Matched posts: {len(report)}")
    print(f"Report written: {REPORT_FILE}")

    for item in report:
        print(
            f"{item['id']}\t{item['top_category']}\tsegments={item['changed_segments']}\t{item['title']}"
        )

    if not args.apply:
        return

    apply_updates(session, report, args)


if __name__ == "__main__":
    main()
