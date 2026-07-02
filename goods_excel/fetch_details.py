"""
网易严选商品采集工具（协程并发版）
用法: python3 fetch_details.py <关键词> [--size 20] [--concurrency 5]
示例: python3 fetch_details.py 非遗
      python3 fetch_details.py 茶具 --size 40 --concurrency 8
"""
import asyncio
import json
import re
import sys
import time
import argparse
import httpx
from openpyxl import Workbook
from html import escape as html_escape

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
}
MAX_RETRIES = 3


# ── 1. 搜索接口（只调一次，保留同步即可） ──

def search_goods(keyword: str, size: int = 20) -> list:
    """调用网易严选搜索接口，返回商品ID+名称列表"""
    url = "https://you.163.com/xhr/search/search.json"
    params = {
        "csrf_token": "",
        "__timestamp": int(time.time() * 1000),
        "page": 1,
        "sortType": 0,
        "categoryId": 0,
        "descSorted": "true",
        "matchType": 0,
        "floorPrice": -1,
        "upperPrice": -1,
        "stillSearch": "false",
        "searchWordSource": 1,
        "size": size,
        "keyword": keyword,
        "needPopWindow": "true",
    }
    resp = httpx.get(url, params=params, headers={"User-Agent": UA},
                     timeout=15, verify=False)
    resp.raise_for_status()
    data = resp.json()

    if data.get("code") != "200":
        print(f"搜索接口返回异常: {data.get('code')}")
        return []

    items = (data.get("data", {})
             .get("directly", {})
             .get("searcherResult", {})
             .get("result", []))

    return [{"id": item["id"], "name": item.get("name", "")} for item in items]


# ── 2. 异步网络请求（重试 + 指数退避） ──

async def fetch_html(client: httpx.AsyncClient, url: str) -> str:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = await client.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            if not resp.text:
                raise Exception("响应内容为空")
            return resp.text
        except Exception as e:
            if attempt == MAX_RETRIES:
                raise
            delay = 2 ** (attempt - 1)
            print(f"  重试 {attempt}/{MAX_RETRIES}: {e}, {delay}s后重试")
            await asyncio.sleep(delay)


# ── 3. JSON 提取（引号感知括号匹配） ──

def extract_json_string(html: str) -> str | None:
    marker = "JSON_DATA_FROMFTL = "
    start_pos = html.find(marker)
    if start_pos == -1:
        return None

    json_start = start_pos + len(marker)
    brace_count = 0
    in_double_quote = False
    in_single_quote = False
    escape_next = False
    end_pos = json_start

    for i in range(json_start, len(html)):
        ch = html[i]
        if escape_next:
            escape_next = False
            continue
        if ch == '\\':
            escape_next = True
            continue
        if ch == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
            continue
        if ch == "'" and not in_double_quote:
            in_single_quote = not in_single_quote
            continue
        if not in_double_quote and not in_single_quote:
            if ch == '{':
                brace_count += 1
            elif ch == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_pos = i + 1
                    break

    return html[json_start:end_pos]


# ── 4. JSON 修复（单引号→双引号） ──

def parse_json(json_str: str) -> dict | None:
    if not json_str:
        return None
    json_str = re.sub(r":\s*'([^']*)'", r': "\1"', json_str)
    json_str = re.sub(r"'([^']+)':", r'"\1":', json_str)
    return json.loads(json_str)


# ── 5. 数据清洗 ──

def clean_product(data: dict) -> dict | None:
    item = data.get("item")
    if not item:
        return None

    prices = []
    if isinstance(item.get("skuList"), list):
        for sku in item["skuList"]:
            p = sku.get("retailPrice") or sku.get("price")
            if p and p > 0:
                prices.append(p)
    elif isinstance(item.get("skuMap"), dict):
        for sku in item["skuMap"].values():
            p = sku.get("retailPrice") or sku.get("activityPrice") or sku.get("limitPrice")
            if p and p > 0:
                prices.append(p)

    max_price = max(prices) if prices else 0
    min_price = min(prices) if prices else 0

    desc_html = ""
    if isinstance(item.get("attrList"), list):
        desc_html = '<div class="product-description">'
        for attr in item["attrList"]:
            name = attr.get("attrName", "")
            value = attr.get("attrValue", "")
            if name and value:
                desc_html += f"<p><strong>{html_escape(name)}</strong>：{html_escape(value)}</p>"
        desc_html += "</div>"

    plain_len = len(re.sub(r"<[^>]+>", "", desc_html))
    detail_html = (item.get("itemDetail") or {}).get("detailHtml", "")
    if plain_len < 200 and detail_html:
        desc_html += f'<div class="product-detail">{detail_html}</div>'

    return {
        "id": item.get("id"),
        "name": item.get("name", ""),
        "simpleDesc": item.get("simpleDesc", ""),
        "primaryPicUrl": item.get("primaryPicUrl", ""),
        "minPrice": min_price,
        "description": desc_html,
    }


# ── 6. 单个商品抓取（异步） ──

async def fetch_one(client: httpx.AsyncClient, goods_id: int) -> dict | None:
    url = f"https://you.163.com/item/detail?id={goods_id}"
    html = await fetch_html(client, url)
    json_str = extract_json_string(html)
    if not json_str:
        return None
    data = parse_json(json_str)
    return clean_product(data)


# ── 7. 导出 Excel ──

def export_excel(items: list, keyword: str):
    filename = f"goods_{keyword}.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "商品列表"

    headers = ["id", "title", "image", "price_min", "subtitle", "description"]
    ws.append(headers)

    col_widths = [12, 40, 50, 12, 50, 80]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[ws.cell(1, i).column_letter].width = w

    for item in items:
        ws.append([
            item["id"],
            item["name"],
            item.get("primaryPicUrl", ""),
            item["minPrice"],
            item["simpleDesc"],
            item["description"],
        ])

    wb.save(filename)
    print(f"Excel 已保存: {filename}")


# ── 主流程（异步） ──

async def amain():
    parser = argparse.ArgumentParser(description="网易严选商品采集 → Excel（协程并发）")
    parser.add_argument("keyword", help="搜索关键词")
    parser.add_argument("--size", type=int, default=20, help="搜索数量 (默认20)")
    parser.add_argument("--concurrency", type=int, default=5, help="并发数 (默认5)")
    args = parser.parse_args()

    keyword = args.keyword
    concurrency = max(1, args.concurrency)
    started_at = time.perf_counter()
    start_time_str = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"开始时间: {start_time_str}")
    print(f"搜索关键词: {keyword}, 数量: {args.size}, 并发: {concurrency}")

    # Step 1: 搜索
    print("\n[1/3] 搜索商品列表...")
    goods = search_goods(keyword, args.size)
    if not goods:
        print("未搜索到商品，退出")
        sys.exit(1)
    print(f"  找到 {len(goods)} 个商品")

    # Step 2: 并发抓取详情
    print(f"\n[2/3] 并发抓取商品详情（最多 {concurrency} 个同时）...")
    semaphore = asyncio.Semaphore(concurrency)
    results: list[dict] = []

    async def _fetch_one(g: dict, idx: int, total: int):
        async with semaphore:
            print(f"  [{idx}/{total}] {g['name'][:30]} ... ", end="", flush=True)
            try:
                item = await fetch_one(client, g["id"])
                if item:
                    results.append(item)
                    print(f"OK ¥{item['minPrice']}")
                else:
                    print("跳过(无数据)")
            except Exception as e:
                print(f"失败: {e}")

    async with httpx.AsyncClient(verify=False) as client:
        tasks = [
            _fetch_one(g, i + 1, len(goods))
            for i, g in enumerate(goods)
        ]
        await asyncio.gather(*tasks)

    # Step 3: 导出
    print(f"\n[3/3] 导出 Excel...")
    export_excel(results, keyword)
    elapsed = time.perf_counter() - started_at
    end_time_str = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"结束时间: {end_time_str}")
    print(f"完成: {len(results)}/{len(goods)} 条，总耗时 {elapsed:.1f} 秒")


def main():
    asyncio.run(amain())


if __name__ == "__main__":
    main()
