from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import quote


if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parent.parent))

from ai_goods_pipeline.clients.bing_image_client import BingImageClient


def build_bing_search_url(query: str) -> str:
    encoded = quote(query.strip(), safe="")
    return (
        "https://cn.bing.com/images/search"
        f"?q={encoded}&qft=+filterui:imagesize-large&form=IRFLTR&first=1"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify Bing first-screen image order only."
    )
    parser.add_argument("--query", required=True, help="Search query to verify.")
    parser.add_argument(
        "--count",
        "--limit",
        dest="count",
        type=int,
        default=4,
        help="How many Bing first-screen items to print, default: 4.",
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

    print_section("Bing Search URL")
    print(build_bing_search_url(query))

    bing_client = BingImageClient(timeout=args.timeout)
    bing_items = bing_client.fetch_images(query, limit=args.count)

    print_section("Bing First-Screen Items")
    if not bing_items:
        print("No Bing items returned.")
    for index, item in enumerate(bing_items, 1):
        print(f"#{index}")
        print(f"title={item.get('title', '')}")
        print(f"image_url={item.get('image_url', '')}")
        print(f"thumbnail_url={item.get('thumbnail_url', '')}")
        print(f"source_page={item.get('source_page', '')}")
        print()

    bing_client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
