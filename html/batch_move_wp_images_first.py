#!/usr/bin/env python3
"""
Move leading product image blocks before the intro text block in WordPress posts.

Scope:
- only the three configured parent categories and their child categories
- only posts whose content starts with:
  1. one intro block
  2. followed by one or more image-only <p> blocks

Default mode is dry-run. Use --apply to update existing posts.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import requests


WP_API_BASE = "https://www.zgzonre.com/wp-json/wp/v2"
TARGET_CATEGORY_IDS = [37, 38, 39, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 67]
DEFAULT_TIMEOUT = 30
DEFAULT_SLEEP_SECONDS = 0.4
REPORT_FILE = Path("out/image_first_report.json")
BACKUP_DIR = Path("out/image_first_backup")

ARTVIEW_DIV_PATTERN = re.compile(
    r"^\s*(?P<intro><div\b[^>]*class=[\"'][^\"']*artview_detail[^\"']*[\"'][^>]*>[\s\S]*?</div>)"
    r"(?P<images>(?:\s*<p\b[^>]*>\s*(?:<a\b[^>]*>\s*)?<img\b[\s\S]*?(?:</a>\s*)?</p>)+)"
    r"(?P<rest>[\s\S]*)$",
    re.I,
)
TEXT_P_PATTERN = re.compile(
    r"^\s*(?P<intro><p\b[^>]*>[\s\S]*?</p>)"
    r"(?P<images>(?:\s*<p\b[^>]*>\s*(?:<a\b[^>]*>\s*)?<img\b[\s\S]*?(?:</a>\s*)?</p>)+)"
    r"(?P<rest>[\s\S]*)$",
    re.I,
)
IMAGE_P_ONLY_RE = re.compile(
    r"^\s*<p\b[^>]*>\s*(?:<a\b[^>]*>\s*)?<img\b[\s\S]*?(?:</a>\s*)?</p>\s*$",
    re.I,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Move leading image blocks before intro text for selected WP product posts."
    )
    parser.add_argument("--apply", action="store_true", help="Update existing posts.")
    parser.add_argument("--ids", type=str, help="Comma-separated post IDs.")
    parser.add_argument("--limit", type=int, default=0, help="Only process the first N matches.")
    parser.add_argument(
        "--sleep",
        type=float,
        default=DEFAULT_SLEEP_SECONDS,
        help="Seconds to sleep between write requests.",
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
    session.headers.update({"User-Agent": "wp-image-first-migrator/1.0"})
    return session


def parse_ids(raw_ids: Optional[str]) -> Optional[set[int]]:
    if not raw_ids:
        return None
    values: set[int] = set()
    for chunk in raw_ids.split(","):
        chunk = chunk.strip()
        if chunk:
            values.add(int(chunk))
    return values


def fetch_target_posts(session: requests.Session) -> List[Dict[str, object]]:
    posts: List[Dict[str, object]] = []
    page = 1

    while True:
        response = session.get(
            f"{WP_API_BASE}/posts",
            params={
                "categories": ",".join(str(item) for item in TARGET_CATEGORY_IDS),
                "per_page": 100,
                "page": page,
                "_fields": "id,title,categories,content,date",
            },
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
        page_items = response.json()
        posts.extend(page_items if isinstance(page_items, list) else [])
        total_pages = int(response.headers.get("X-WP-TotalPages", "1"))
        if page >= total_pages:
            break
        page += 1

    return posts


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


def count_leading_images(html: str) -> int:
    count = 0
    for match in re.finditer(r"<p\b[^>]*>[\s\S]*?</p>", html, flags=re.I):
        if IMAGE_P_ONLY_RE.match(match.group(0)):
            count += 1
    return count


def reorder_content(html: str) -> Tuple[str, Dict[str, object]]:
    if not html.strip():
        return html, {"matched": False, "reason": "empty"}

    for pattern_name, pattern in (("artview_div", ARTVIEW_DIV_PATTERN), ("text_p", TEXT_P_PATTERN)):
        match = pattern.match(html)
        if not match:
            continue

        intro = match.group("intro")
        images = match.group("images")
        rest = match.group("rest")
        image_count = count_leading_images(images)
        if image_count <= 0:
            return html, {"matched": False, "reason": "no_image_blocks"}

        reordered = images.strip() + "\n" + intro.strip()
        if rest.strip():
            reordered += "\n" + rest.strip()

        return reordered, {
            "matched": True,
            "pattern": pattern_name,
            "image_count": image_count,
        }

    if re.match(r"^\s*<p\b[^>]*>\s*(?:<a\b[^>]*>\s*)?<img\b", html, flags=re.I):
        return html, {"matched": False, "reason": "already_image_first"}

    return html, {"matched": False, "reason": "unsupported_structure"}


def build_report(posts: Iterable[Dict[str, object]]) -> List[Dict[str, object]]:
    report: List[Dict[str, object]] = []
    for post in posts:
        original_html = rendered_content(post)
        reordered_html, meta = reorder_content(original_html)
        if reordered_html == original_html:
            continue
        report.append(
            {
                "id": int(post["id"]),
                "title": title_text(post),
                "pattern": meta["pattern"],
                "image_count": meta["image_count"],
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
    response = session.get(
        f"{WP_API_BASE}/posts/{post_id}",
        params={"context": "edit"},
        auth=auth,
        timeout=DEFAULT_TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError(f"Unexpected response for post {post_id}")
    return payload


def save_backup(post_id: int, title: str, before_html: str, after_html: str) -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    (BACKUP_DIR / f"{post_id}.meta.json").write_text(
        json.dumps({"id": post_id, "title": title}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (BACKUP_DIR / f"{post_id}.before.html").write_text(before_html, encoding="utf-8")
    (BACKUP_DIR / f"{post_id}.after.html").write_text(after_html, encoding="utf-8")


def update_post_content(
    session: requests.Session,
    post_id: int,
    html: str,
    auth: Tuple[str, str],
) -> None:
    response = session.post(
        f"{WP_API_BASE}/posts/{post_id}",
        auth=auth,
        json={"content": html},
        timeout=DEFAULT_TIMEOUT,
    )
    response.raise_for_status()


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
        reordered_html, meta = reorder_content(original_html)
        if reordered_html == original_html:
            print(f"[skip] {post_id} no reorder needed")
            continue
        save_backup(post_id, title_text(post), original_html, reordered_html)
        update_post_content(session, post_id, reordered_html, auth)
        print(
            f"[updated] {index}/{len(report)} post_id={post_id} images={meta['image_count']} pattern={meta['pattern']} title={title_text(post)}"
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
            f"{item['id']}\timages={item['image_count']}\tpattern={item['pattern']}\t{item['title']}"
        )

    if not args.apply:
        return

    apply_updates(session, report, args)


if __name__ == "__main__":
    main()
