from __future__ import annotations

from pathlib import Path

import pymysql


if __package__ in {None, ""}:
    import sys

    sys.path.append(str(Path(__file__).resolve().parent.parent))

from ai_goods_pipeline.config import load_settings


def ensure_column(cursor, *, table: str, column: str, ddl: str) -> None:
    cursor.execute(f"SHOW COLUMNS FROM `{table}` LIKE %s", (column,))
    if cursor.fetchone():
        return
    cursor.execute(f"ALTER TABLE `{table}` ADD COLUMN {ddl}")


def ensure_index(cursor, *, table: str, index_name: str, ddl: str) -> None:
    cursor.execute(f"SHOW INDEX FROM `{table}` WHERE Key_name = %s", (index_name,))
    if cursor.fetchone():
        return
    cursor.execute(f"ALTER TABLE `{table}` ADD INDEX {ddl}")


def main() -> int:
    settings = load_settings()
    conn = pymysql.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
        charset=settings.db_charset,
        autocommit=False,
    )
    try:
        with conn.cursor() as cursor:
            ensure_column(
                cursor,
                table=settings.db_table,
                column="batch_id",
                ddl="`batch_id` varchar(32) NOT NULL DEFAULT '' COMMENT '首次入库批次号' AFTER `en_name`",
            )
            ensure_column(
                cursor,
                table=settings.db_table,
                column="last_batch_id",
                ddl="`last_batch_id` varchar(32) NOT NULL DEFAULT '' COMMENT '最近一次处理批次号' AFTER `batch_id`",
            )
            ensure_column(
                cursor,
                table=settings.db_table,
                column="source_type",
                ddl="`source_type` varchar(20) NOT NULL DEFAULT '' COMMENT '首次来源类型' AFTER `last_batch_id`",
            )
            ensure_column(
                cursor,
                table=settings.db_table,
                column="source_note",
                ddl="`source_note` varchar(255) NOT NULL DEFAULT '' COMMENT '来源备注' AFTER `source_type`",
            )
            ensure_index(
                cursor,
                table=settings.db_table,
                index_name="idx_batch_id",
                ddl="`idx_batch_id` (`batch_id`)",
            )
            ensure_index(
                cursor,
                table=settings.db_table,
                index_name="idx_last_batch_id",
                ddl="`idx_last_batch_id` (`last_batch_id`)",
            )
            ensure_index(
                cursor,
                table=settings.db_table,
                index_name="idx_source_type",
                ddl="`idx_source_type` (`source_type`)",
            )
            ensure_index(
                cursor,
                table=settings.db_table,
                index_name="idx_category_create_time",
                ddl="`idx_category_create_time` (`category_id`, `create_time`)",
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print(f"ok table={settings.db_table}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
