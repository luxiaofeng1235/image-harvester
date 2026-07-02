from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

try:
    import aiomysql
except ImportError:  # pragma: no cover - optional runtime dependency
    aiomysql = None

logger = logging.getLogger(__name__)


class AsyncDBWriter:
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
        pool_minsize: int = 1,
        pool_maxsize: int = 10,
    ) -> None:
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.charset = charset
        self.table = table
        self.pool_minsize = pool_minsize
        self.pool_maxsize = pool_maxsize
        self._pool = None
        self._pool_lock = asyncio.Lock()

    async def close(self) -> None:
        if self._pool is not None:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None

    async def fetch_existing_titles(self, max_recent_count: int = 2000) -> list[str]:
        """拉取最近 N 条商品标题作为去重基线。

        优化：原实现拉全表（SELECT goods_name WHERE ...），随数据增长变慢。
        改为只拉最近 max_recent_count 条（按 id 降序），足够覆盖近期去重。
        如果表里确实有大量历史数据，更早期的标题已不太可能被重复生成。
        """
        pool = await self._get_pool()
        sql = (
            f"SELECT goods_name FROM `{self.table}` "
            f"WHERE goods_name IS NOT NULL AND goods_name <> '' "
            f"ORDER BY id DESC LIMIT %s"
        )
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(sql, (max_recent_count,))
                rows = await cursor.fetchall()
        return [str(row[0]).strip() for row in rows if row and str(row[0]).strip()]

    async def insert_goods(self, goods_records: list[dict[str, Any]]) -> int:
        if not goods_records:
            return 0

        pool = await self._get_pool()
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
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(sql, flat_params)
            await conn.commit()
        return len(goods_records)

    async def fetch_goods_for_enrichment(
        self,
        *,
        category_id: int | None = None,
        limit: int = 20,
        missing_mode: str = "either",
        ids: list[int] | None = None,
    ) -> list[dict[str, Any]]:
        pool = await self._get_pool()
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
                id, goods_name, sub_title, category_id, image, price, description,
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

        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                await cursor.execute(sql, params)
                rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def update_goods_enrichment(
        self,
        *,
        goods_id: int,
        sub_title: str | None = None,
        image: str | None = None,
        description: str | None = None,
        last_batch_id: str | None = None,
    ) -> int:
        pool = await self._get_pool()
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
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                affected = await cursor.execute(sql, params)
            await conn.commit()
        return int(affected)


    async def _get_pool(self):
        if aiomysql is None:
            raise RuntimeError("aiomysql_not_installed")
        if self._pool is not None:
            return self._pool
        async with self._pool_lock:
            if self._pool is not None:
                return self._pool
            try:
                self._pool = await aiomysql.create_pool(
                    host=self.host,
                    port=self.port,
                    user=self.user,
                    password=self.password,
                    db=self.database,
                    charset=self.charset,
                    autocommit=False,
                    minsize=self.pool_minsize,
                    maxsize=self.pool_maxsize,
                )
                logger.info("DB pool created host=%s db=%s pool_max=%s", self.host, self.database, self.pool_maxsize)
                return self._pool
            except Exception as exc:
                logger.error("DB pool create failed host=%s db=%s error=%s", self.host, self.database, exc)
                raise

    def _build_missing_condition(self, missing_mode: str) -> str:
        image_empty = "(image IS NULL OR image = '')"
        description_empty = "(description IS NULL OR description = '')"
        mode = (missing_mode or "either").strip().lower()
        if mode == "none":
            return ""
        if mode == "image":
            return image_empty
        if mode == "description":
            return description_empty
        if mode == "both":
            return f"{image_empty} AND {description_empty}"
        return f"({image_empty} OR {description_empty})"
