# 网易严选商品采集工具

**文件**: `goods_excel/fetch_details.py`  
**架构**: 协程版（`asyncio` + `httpx.AsyncClient`）  
**并发模型**: 默认 5 个商品同时抓取，`Semaphore` 限流，速度比串行快 3~5 倍

---

## 程序流程

```
┌─ 搜索 ─────────────────────────────────────────┐
│  httpx 请求网易严选搜索API                       │
│  → 返回商品 ID + 名称列表                       │
└──────────────────────┬──────────────────────────┘
                       ↓
┌─ 并发抓取详情（协程核心） ───────────────────────┐
│  asyncio.gather 并发调度                         │
│  Semaphore(5) 控制同时请求数                     │
│  httpx.AsyncClient 异步 HTTP 请求               │
│  retry 指数退避（3次重试）                       │
│  每个商品: 下载HTML → 提取JSON → 清洗数据        │
└──────────────────────┬──────────────────────────┘
                       ↓
┌─ 导出 Excel ────────────────────────────────────┐
│  openpyxl 写入 goods_{关键词}.xlsx               │
│  列: id / title / image / price_min             │
│      / subtitle / description                   │
└─────────────────────────────────────────────────┘
```

**协程关键点**:
- `async def fetch_html()` → 异步 HTTP 请求，不阻塞事件循环
- `async def fetch_one()` → 单个商品抓取流程（异步）
- `asyncio.gather(*tasks)` → 所有商品并发执行
- `asyncio.Semaphore(concurrency)` → 限制并发数，避免被封

---

## 用法

```bash
cd /mnt/d/python_work/image-harvester/goods_excel

python3 fetch_details.py <关键词> [--size 数量] [--concurrency 并发数]
```

### 示例

```bash
# 默认并发 5，采集 40 个
python3 fetch_details.py 非遗

# 指定数量和并发
python3 fetch_details.py 茶具 --size 60 --concurrency 10

# 怕被反爬就调小并发
python3 fetch_details.py 紫砂 --size 20 --concurrency 3
```

### 参数

| 参数 | 说明 | 默认 |
|---|---|---|
| `关键词` | 搜索词（必填） | — |
| `--size` | 采集商品数量 | 40 |
| `--concurrency` | 并发请求数 | 5 |

---

## 输出

```bash
goods_非遗.xlsx
goods_茶具.xlsx
goods_紫砂.xlsx
```

## 依赖

```bash
pip install httpx openpyxl
```

两个都在项目 `requirements.txt` 里，不需要额外安装。
