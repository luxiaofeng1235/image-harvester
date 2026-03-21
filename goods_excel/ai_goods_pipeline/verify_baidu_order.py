from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import quote


if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parent.parent))

from ai_goods_pipeline.clients.baidu_image_client import BaiduImageClient


def build_baidu_search_url(query: str) -> str:
    encoded = quote(query.strip(), safe="")
    return (
        "https://image.baidu.com/search/index"
        f"?tn=baiduimage&fm=result&ie=utf-8&word={encoded}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify Baidu first-screen image order only."
    )
    parser.add_argument("--query", required=True, help="Search query to verify.")
    parser.add_argument(
        "--count",
        "--limit",
        dest="count",
        type=int,
        default=4,
        help="How many Baidu first-screen items to print, default: 4.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=20,
        help="Request/browser timeout in seconds, default: 20.",
    )
    return parser.parse_args()


def print_section(title: str) -> None:
    print(f"\n=== {title} ===")


def main() -> int:
    args = parse_args()
    query = args.query.strip()
    if not query:
        raise SystemExit("--query must not be empty")
    if args.count <= 0:
        raise SystemExit("--count must be > 0")

    print_section("Baidu Search URL")
    print(build_baidu_search_url(query))

    baidu_client = BaiduImageClient(timeout=args.timeout)
    baidu_items = baidu_client.fetch_images(query, limit=args.count)

    print_section("Baidu First-Screen Items")
    if not baidu_items:
        print("No Baidu items returned.")
    for index, item in enumerate(baidu_items, 1):
        print(f"#{index}")
        print(f"title={item.get('title', '')}")
        print(f"pn={item.get('pn', '')}")
        print(f"image_url={item.get('image_url', '')}")
        print(f"raw_image_url={item.get('raw_image_url', '')}")
        print(f"thumbnail_url={item.get('thumbnail_url', '')}")
        print(f"source_page={item.get('source_page', '')}")
        print(f"bdtype={item.get('bdtype', '')}")
        print(f"resolved_from={item.get('resolved_from', '')}")
        print()

    baidu_client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
