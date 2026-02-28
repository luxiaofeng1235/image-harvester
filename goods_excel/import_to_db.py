"""将4个Excel导入 jj_wangyi_goods 表"""
import time
import pymysql
from openpyxl import load_workbook

DB_CONFIG = {
    "host": "localhost",
    "user": "*",
    "password": "*",
    "database": "jiujie_shop",
    "charset": "utf8mb4",
}

FILES = [
    (126, "goods_江苏特产.xlsx"),
    (127, "goods_非遗.xlsx"),
    (128, "goods_AI科技.xlsx"),
    (129, "goods_苏超纪念品.xlsx"),
]

SQL = """INSERT INTO jj_wangyi_goods
    (goods_name, sub_title, category_id, image, price, description, create_time, update_time)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"""


def main():
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor()
    now = int(time.time())
    total = 0

    for cat_id, fname in FILES:
        wb = load_workbook(fname)
        ws = wb.active
        count = 0
        for row in range(2, ws.max_row + 1):
            title = ws.cell(row, 2).value or ""
            image = ws.cell(row, 3).value or ""
            price = ws.cell(row, 4).value or 0
            subtitle = ws.cell(row, 5).value or ""
            desc = ws.cell(row, 6).value or ""

            cursor.execute(SQL, (title, subtitle, cat_id, image, price, desc, now, now))
            count += 1

        conn.commit()
        total += count
        print(f"分类{cat_id} | {fname} | 导入 {count} 条")

    cursor.close()
    conn.close()
    print(f"\n完成，共导入 {total} 条")


if __name__ == "__main__":
    main()
