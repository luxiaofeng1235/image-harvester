from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path


if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parent.parent))

from ai_goods_pipeline.config import load_settings
from ai_goods_pipeline.writers.db_writer import DBWriter


CATEGORY_NAMES = {
    126: "江苏特产",
    127: "农副产品",
    128: "苏超纪念品",
    129: "工艺产品",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build local HTML report for image review.")
    parser.add_argument("--output", type=str, default="ai_goods_pipeline/runtime/image_review_report.html")
    parser.add_argument("--category-id", type=int, default=0)
    return parser.parse_args()


def fetch_rows(category_id: int | None) -> list[dict[str, object]]:
    settings = load_settings()
    db = DBWriter(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
        charset=settings.db_charset,
        table=settings.db_table,
    )
    sql = """
        SELECT id, goods_name, category_id, price, image, sub_title
        FROM jj_wangyi_goods
        WHERE image IS NOT NULL AND image <> ''
    """
    params: list[object] = []
    if category_id:
        sql += " AND category_id = %s"
        params.append(category_id)
    sql += " ORDER BY category_id ASC, id ASC"

    with db._connect() as conn:  # noqa: SLF001 - reuse existing connection config
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
    return [
        {
            "id": int(row[0]),
            "goods_name": str(row[1] or ""),
            "category_id": int(row[2]),
            "price": float(row[3] or 0),
            "image": str(row[4] or ""),
            "sub_title": str(row[5] or ""),
        }
        for row in rows
    ]


def build_card(row: dict[str, object]) -> str:
    goods_id = int(row["id"])
    title = html.escape(str(row["goods_name"]))
    category_id = int(row["category_id"])
    category_name = CATEGORY_NAMES.get(category_id, str(category_id))
    price = float(row["price"])
    image = html.escape(str(row["image"]))
    subtitle = html.escape(str(row["sub_title"] or ""))
    return f"""
    <article class="card category-{category_id}">
      <div class="img-wrap">
        <img loading="lazy" src="{image}" alt="{title}" />
      </div>
      <div class="meta">
        <div class="topline">
          <span class="badge">{category_name}</span>
          <span class="id">ID {goods_id}</span>
        </div>
        <h3>{title}</h3>
        <p class="price">¥{price:.2f}</p>
        <p class="subtitle">{subtitle or "无副标题"}</p>
        <p class="url"><a href="{image}" target="_blank" rel="noreferrer">{image}</a></p>
      </div>
    </article>
    """


def build_html(rows: list[dict[str, object]]) -> str:
    sections: list[str] = []
    for category_id in sorted({int(row["category_id"]) for row in rows}):
        category_rows = [row for row in rows if int(row["category_id"]) == category_id]
        cards = "\n".join(build_card(row) for row in category_rows)
        sections.append(
            f"""
            <section id="category-{category_id}">
              <h2>{CATEGORY_NAMES.get(category_id, category_id)} ({len(category_rows)})</h2>
              <div class="grid">{cards}</div>
            </section>
            """
        )

    body = "\n".join(sections)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>商品主图巡检页</title>
  <style>
    :root {{
      --bg: #f3efe6;
      --panel: #fffaf2;
      --line: #d7cbb7;
      --text: #2f261d;
      --muted: #74675a;
      --accent: #a64b2a;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Noto Serif SC", "Source Han Serif SC", serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(166, 75, 42, 0.08), transparent 30%),
        linear-gradient(180deg, #f7f2e9, var(--bg));
    }}
    header {{
      position: sticky;
      top: 0;
      z-index: 5;
      background: rgba(247, 242, 233, 0.94);
      backdrop-filter: blur(8px);
      border-bottom: 1px solid var(--line);
      padding: 16px 20px;
    }}
    h1 {{ margin: 0 0 8px; font-size: 26px; }}
    nav a {{
      color: var(--accent);
      margin-right: 14px;
      text-decoration: none;
      font-weight: 700;
    }}
    main {{ padding: 20px; }}
    section {{ margin-bottom: 28px; }}
    h2 {{ margin: 0 0 12px; font-size: 22px; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
      gap: 16px;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 16px;
      overflow: hidden;
      box-shadow: 0 10px 30px rgba(60, 45, 30, 0.08);
    }}
    .img-wrap {{
      background: #ece5da;
      aspect-ratio: 1 / 1;
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: hidden;
    }}
    img {{
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
    }}
    .meta {{ padding: 14px; }}
    .topline {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-bottom: 8px;
    }}
    .badge {{
      display: inline-block;
      padding: 4px 10px;
      border-radius: 999px;
      background: #efe1cf;
      color: var(--accent);
      font-size: 12px;
      font-weight: 700;
    }}
    .id {{ color: var(--muted); font-size: 12px; }}
    h3 {{
      margin: 0 0 8px;
      font-size: 18px;
      line-height: 1.45;
    }}
    .price {{
      margin: 0 0 8px;
      color: var(--accent);
      font-weight: 700;
    }}
    .subtitle {{
      margin: 0 0 8px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.5;
      min-height: 2.6em;
    }}
    .url {{
      margin: 0;
      font-size: 12px;
      line-height: 1.5;
      word-break: break-all;
    }}
    .url a {{ color: #355f7d; }}
  </style>
</head>
<body>
  <header>
    <h1>商品主图巡检页</h1>
    <nav>
      <a href="#category-126">126 江苏特产</a>
      <a href="#category-127">127 农副产品</a>
      <a href="#category-128">128 苏超纪念品</a>
      <a href="#category-129">129 工艺产品</a>
    </nav>
  </header>
  <main>
    {body}
  </main>
</body>
</html>
"""


def main() -> int:
    args = parse_args()
    rows = fetch_rows(args.category_id or None)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_html(rows), encoding="utf-8")
    print(output)
    print(f"rows={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
