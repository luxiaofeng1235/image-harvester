from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import pymysql
from pymysql.cursors import DictCursor


if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parent.parent))

from ai_goods_pipeline.clients.oss_client import normalize_object_acl, resolve_object_acl
from ai_goods_pipeline.config import load_settings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch fix OSS object ACL by jj_wangyi_goods image URLs.")
    parser.add_argument("--goods-ids", type=str, default="", help="逗号分隔商品 id")
    parser.add_argument("--category-id", type=int, default=0)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--acl", type=str, default="public-read")
    parser.add_argument("--apply", type=int, default=0)
    return parser.parse_args()


def parse_goods_ids(raw: str) -> list[int]:
    ids: list[int] = []
    for chunk in str(raw or "").split(","):
        text = chunk.strip()
        if not text:
            continue
        ids.append(int(text))
    return ids


def extract_image_urls(description: str) -> list[str]:
    return re.findall(r'<img[^>]+src="([^"]+)"', str(description or ""), re.I)


def build_where_clause(*, goods_ids: list[int], category_id: int, limit: int) -> tuple[str, list[Any], str]:
    where_parts = ["1=1"]
    params: list[Any] = []
    if goods_ids:
        placeholders = ",".join(["%s"] * len(goods_ids))
        where_parts.append(f"id IN ({placeholders})")
        params.extend(goods_ids)
    if category_id > 0:
        where_parts.append("category_id = %s")
        params.append(category_id)
    sql_limit = ""
    if limit > 0:
        sql_limit = " LIMIT %s"
        params.append(limit)
    return " AND ".join(where_parts), params, sql_limit


def fetch_rows(settings, *, goods_ids: list[int], category_id: int, limit: int) -> list[dict[str, Any]]:
    where_sql, params, limit_sql = build_where_clause(
        goods_ids=goods_ids,
        category_id=category_id,
        limit=limit,
    )
    sql = f"""
        SELECT id, goods_name, image, description
        FROM `{settings.db_table}`
        WHERE {where_sql}
        ORDER BY id ASC
        {limit_sql}
    """
    conn = pymysql.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
        charset=settings.db_charset,
        cursorclass=DictCursor,
        autocommit=True,
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            return list(cursor.fetchall())
    finally:
        conn.close()


def collect_object_keys(rows: list[dict[str, Any]], *, view_domain: str) -> tuple[list[str], dict[str, int]]:
    normalized_domain = view_domain.rstrip("/") + "/"
    keys: list[str] = []
    counts = {"main_image": 0, "detail_image": 0, "skipped_non_oss": 0}
    seen: set[str] = set()

    def _push(url: str, *, field: str) -> None:
        text = str(url or "").strip()
        if not text:
            return
        if not text.startswith(normalized_domain):
            counts["skipped_non_oss"] += 1
            return
        key = text[len(normalized_domain):].strip("/")
        if not key or key in seen:
            return
        seen.add(key)
        keys.append(key)
        counts[field] += 1

    for row in rows:
        _push(str(row.get("image") or ""), field="main_image")
        for url in extract_image_urls(str(row.get("description") or "")):
            _push(url, field="detail_image")
    return keys, counts


def main() -> int:
    args = parse_args()
    settings = load_settings()
    acl_name = normalize_object_acl(args.acl)
    acl_permission = resolve_object_acl(acl_name)
    if acl_permission is None:
        raise SystemExit("--acl 不能是 inherit/default/bucket，批量修复请传 public-read 或 private")
    goods_ids = parse_goods_ids(args.goods_ids)
    rows = fetch_rows(
        settings,
        goods_ids=goods_ids,
        category_id=args.category_id,
        limit=args.limit,
    )
    object_keys, counts = collect_object_keys(rows, view_domain=settings.oss_view_domain)
    print(
        f"rows={len(rows)} object_keys={len(object_keys)} "
        f"main_images={counts['main_image']} detail_images={counts['detail_image']} "
        f"skipped_non_oss={counts['skipped_non_oss']} acl={acl_name}"
    )
    if object_keys:
        preview = object_keys[:10]
        print("preview_keys=" + ",".join(preview))
    else:
        print("preview_keys=")

    if not args.apply:
        print("dry_run=1 apply=0")
        return 0

    from ai_goods_pipeline.clients.oss_client import OSSImageUploader

    uploader = OSSImageUploader(
        enabled=settings.oss_enabled,
        access_key_id=settings.oss_access_key_id,
        access_key_secret=settings.oss_access_key_secret,
        bucket_name=settings.oss_bucket,
        endpoint=settings.oss_endpoint,
        view_domain=settings.oss_view_domain,
        prefix=settings.oss_prefix,
        object_acl=acl_name,
    )
    if not uploader.enabled or uploader.bucket is None:
        raise SystemExit("oss_not_enabled_or_config_missing")

    updated = 0
    failed = 0
    for key in object_keys:
        try:
            uploader.bucket.put_object_acl(key, acl_permission)
            updated += 1
        except Exception as exc:
            failed += 1
            print(f"acl_failed key={key} error={exc}")

    uploader.close()
    print(f"apply=1 updated={updated} failed={failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
