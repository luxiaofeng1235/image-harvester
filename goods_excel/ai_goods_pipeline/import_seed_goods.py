from __future__ import annotations

import argparse
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parent.parent))

from ai_goods_pipeline.config import load_settings
from ai_goods_pipeline.enums.source_types import SOURCE_SEED_IMPORT
from ai_goods_pipeline.utils.batch_meta import build_source_note, normalize_batch_id
from ai_goods_pipeline.writers.db_writer import DBWriter


LINE_PATTERN = re.compile(r"^(?P<title>.+?)\s+(?P<price>\d+(?:\.\d{1,2})?)$")


@dataclass(slots=True)
class SeedItem:
    title: str
    price: float


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import seed goods by title and price.")
    parser.add_argument("--category-id", type=int, required=True)
    parser.add_argument("--input-file", type=str, default="")
    parser.add_argument("--dry-run", type=int, default=0)
    parser.add_argument("--skip-existing", type=int, default=1)
    parser.add_argument("--batch-id", type=str, default="")
    parser.add_argument("--source-note", type=str, default="")
    return parser.parse_args()


def load_lines(input_file: str) -> list[str]:
    if input_file:
        return Path(input_file).read_text(encoding="utf-8").splitlines()
    return sys.stdin.read().splitlines()


def parse_seed_items(lines: list[str]) -> list[SeedItem]:
    items: list[SeedItem] = []
    for index, raw_line in enumerate(lines, 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = LINE_PATTERN.match(line)
        if not match:
            raise ValueError(f"Line {index} invalid: {raw_line}")
        items.append(
            SeedItem(
                title=match.group("title").strip(),
                price=float(match.group("price")),
            )
        )
    if not items:
        raise ValueError("No valid seed items found.")
    return items


def build_records(
    category_id: int,
    items: list[SeedItem],
    *,
    batch_id: str,
    source_note: str,
) -> list[dict[str, object]]:
    now = int(time.time())
    records: list[dict[str, object]] = []
    for item in items:
        records.append(
            {
                "goods_name": item.title,
                "sub_title": "",
                "category_id": category_id,
                "image": "",
                "price": item.price,
                "description": "",
                "en_name": "",
                "batch_id": batch_id,
                "last_batch_id": batch_id,
                "source_type": SOURCE_SEED_IMPORT,
                "source_note": source_note,
                "create_time": now,
                "update_time": now,
            }
        )
    return records


def main() -> int:
    args = parse_args()
    settings = load_settings()
    db_writer = DBWriter(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
        charset=settings.db_charset,
        table=settings.db_table,
    )
    batch_id = normalize_batch_id(
        args.batch_id,
        fallback=datetime.now().strftime("%Y%m%d_%H%M%S"),
    )

    items = parse_seed_items(load_lines(args.input_file))
    existing_titles = set(db_writer.fetch_existing_titles()) if args.skip_existing else set()
    skipped_titles: list[str] = []
    ready_items: list[SeedItem] = []
    for item in items:
        if item.title in existing_titles:
            skipped_titles.append(item.title)
            continue
        ready_items.append(item)

    source_note = build_source_note(
        [
            args.source_note,
            f"input={Path(args.input_file).name}" if args.input_file else "input=stdin",
        ]
    )
    records = build_records(
        args.category_id,
        ready_items,
        batch_id=batch_id,
        source_note=source_note,
    )
    inserted_count = 0
    if not args.dry_run and records:
        inserted_count = db_writer.insert_goods(records)

    print(
        f"batch_id={batch_id} parsed={len(items)} ready={len(records)} inserted={inserted_count} "
        f"skipped={len(skipped_titles)} dry_run={bool(args.dry_run)}"
    )
    if skipped_titles:
        print("skipped_titles=")
        for title in skipped_titles:
            print(title)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
