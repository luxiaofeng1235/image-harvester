from __future__ import annotations

import json
import time
from typing import Any

import pymysql
from pymysql.cursors import DictCursor


class DBWriter:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str,
        charset: str,
        table: str,
    ) -> None:
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.charset = charset
        self.table = table

    def _connect(self):
        return pymysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.database,
            charset=self.charset,
            autocommit=False,
        )

    def fetch_existing_titles(self) -> list[str]:
        sql = f"SELECT goods_name FROM `{self.table}` WHERE goods_name IS NOT NULL AND goods_name <> ''"
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql)
                rows = cursor.fetchall()
        return [str(row[0]).strip() for row in rows if row and str(row[0]).strip()]

    def insert_goods(self, goods_records: list[dict[str, Any]]) -> int:
        if not goods_records:
            return 0

        columns = (
            "goods_name, sub_title, shop_id, category_id, image, price, description, en_name, "
            "batch_id, last_batch_id, source_type, source_note, create_time, update_time, "
            "selling_points, attrs, image_keywords, detail_images, "
            "model_used, main_image_source, detail_image_sources, source_queries, "
            "processing_duration_seconds"
        )
        value_rows: list[str] = []
        flat_params: list[Any] = []
        for item in goods_records:
            placeholders = ",".join(["%s"] * 23)
            value_rows.append(f"({placeholders})")
            flat_params.extend([
                item["goods_name"],
                item["sub_title"],
                int(item.get("shop_id", 0) or 0),
                item["category_id"],
                item["image"],
                item["price"],
                item["description"],
                item.get("en_name", ""),
                item.get("batch_id", ""),
                item.get("last_batch_id", item.get("batch_id", "")),
                item.get("source_type", ""),
                item.get("source_note", ""),
                item["create_time"],
                item["update_time"],
                json.dumps(item.get("selling_points", []), ensure_ascii=False),
                json.dumps(item.get("attrs", {}), ensure_ascii=False),
                json.dumps(item.get("image_keywords", []), ensure_ascii=False),
                json.dumps(item.get("detail_images", []), ensure_ascii=False),
                item.get("model_used", ""),
                item.get("main_image_source", ""),
                json.dumps(item.get("detail_image_sources", []), ensure_ascii=False),
                json.dumps(item.get("source_queries", []), ensure_ascii=False),
                item.get("processing_duration_seconds", 0),
            ])

        sql = f"INSERT INTO `{self.table}` ({columns}) VALUES {', '.join(value_rows)}"
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, flat_params)
            conn.commit()
        return len(goods_records)

    def fetch_goods_for_enrichment(
        self,
        *,
        category_id: int | None = None,
        limit: int = 20,
        missing_mode: str = "either",
        ids: list[int] | None = None,
    ) -> list[dict[str, Any]]:
        where_clauses = ["1=1"]
        params: list[Any] = []

        if category_id is not None:
            where_clauses.append("category_id = %s")
            params.append(category_id)

        if ids:
            placeholders = ",".join(["%s"] * len(ids))
            where_clauses.append(f"id IN ({placeholders})")
            params.extend(ids)

        missing_sql = self._build_missing_condition(missing_mode)
        if missing_sql:
            where_clauses.append(missing_sql)

        sql = f"""
            SELECT
                id, goods_name, sub_title, shop_id, category_id, image, price, description,
                en_name, batch_id, last_batch_id, source_type, source_note, create_time, update_time,
                selling_points, attrs, image_keywords, detail_images,
                model_used, main_image_source, detail_image_sources, source_queries,
                processing_duration_seconds
            FROM `{self.table}`
            WHERE {' AND '.join(where_clauses)}
            ORDER BY id ASC
            LIMIT %s
        """
        params.append(limit)

        with self._connect() as conn:
            with conn.cursor(DictCursor) as cursor:
                cursor.execute(sql, params)
                rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def update_goods_enrichment(
        self,
        *,
        goods_id: int,
        sub_title: str | None = None,
        image: str | None = None,
        description: str | None = None,
        last_batch_id: str | None = None,
    ) -> int:
        fields: list[str] = []
        params: list[Any] = []

        if sub_title is not None:
            fields.append("sub_title = %s")
            params.append(sub_title)
        if image is not None:
            fields.append("image = %s")
            params.append(image)
        if description is not None:
            fields.append("description = %s")
            params.append(description)
        if last_batch_id is not None:
            fields.append("last_batch_id = %s")
            params.append(last_batch_id)

        fields.append("update_time = %s")
        params.append(int(time.time()))
        params.append(goods_id)

        sql = f"UPDATE `{self.table}` SET {', '.join(fields)} WHERE id = %s"
        with self._connect() as conn:
            with conn.cursor() as cursor:
                affected = cursor.execute(sql, params)
            conn.commit()
        return int(affected)


    def _build_missing_condition(self, missing_mode: str) -> str:
        image_empty = "(image IS NULL OR image = '')"
        description_empty = "(description IS NULL OR description = '')"
        mode = (missing_mode or "either").strip().lower()
        if mode == "image":
            return image_empty
        if mode == "description":
            return description_empty
        if mode == "both":
            return f"{image_empty} AND {description_empty}"
        return f"({image_empty} OR {description_empty})"
