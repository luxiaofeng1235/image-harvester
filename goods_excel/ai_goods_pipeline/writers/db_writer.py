from __future__ import annotations

from typing import Any

import pymysql


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

        sql = f"""
            INSERT INTO `{self.table}`
            (goods_name, sub_title, category_id, image, price, description, en_name, create_time, update_time)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = [
            (
                item["goods_name"],
                item["sub_title"],
                item["category_id"],
                item["image"],
                item["price"],
                item["description"],
                item.get("en_name", ""),
                item["create_time"],
                item["update_time"],
            )
            for item in goods_records
        ]

        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.executemany(sql, params)
            conn.commit()
        return len(params)

