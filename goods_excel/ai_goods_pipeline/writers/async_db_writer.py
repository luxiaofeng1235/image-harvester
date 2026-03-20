from __future__ import annotations

import asyncio
import time
from typing import Any

try:
    import aiomysql
except Exception:  # pragma: no cover - optional runtime dependency
    aiomysql = None


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
            SELECT id, goods_name, sub_title, category_id, image, price, description, en_name, create_time, update_time
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
            return self._pool

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
