# 网易严选商品采集工具

**目录**: `goods_excel/`

两个版本：同步版（原始）和协程版（并发优化），功能完全一致。

---

## 文件说明

| 文件 | 版本 | 并发 | 适用场景 |
|---|---|---|---|
| `fetch_details_sync.py` | 同步版 | 无，串行 1 个接 1 个 | 怕被封、网络不稳定、调试用 |
| `fetch_details.py` | 协程版 | 默认 5 个并发 | 量大、网好、追求速度 |

---

## 用法

### 同步版（原始）

```bash
python3 fetch_details_sync.py <关键词> [--size 数量]
```

示例：

```bash
cd /mnt/d/python_work/image-harvester/goods_excel

python3 fetch_details_sync.py 非遗
python3 fetch_details_sync.py 茶具 --size 20
python3 fetch_details_sync.py 江苏特产 --size 60
```

参数：

| 参数 | 说明 | 默认 |
|---|---|---|
| `关键词` | 搜索词（必填） | — |
| `--size` | 采集商品数量 | 40 |

---

### 协程版（推荐）

```bash
python3 fetch_details.py <关键词> [--size 数量] [--concurrency 并发数]
```

示例：

```bash
cd /mnt/d/python_work/image-harvester/goods_excel

# 默认并发 5
python3 fetch_details.py 非遗

# 调大并发（网好时）
python3 fetch_details.py 茶具 --size 60 --concurrency 10

# 调小并发（怕被反爬）
python3 fetch_details.py 紫砂 --size 20 --concurrency 3
```

参数：

| 参数 | 说明 | 默认 |
|---|---|---|
| `关键词` | 搜索词（必填） | — |
| `--size` | 采集商品数量 | 40 |
| `--concurrency` | 并发请求数 | 5 |

---

## 流程说明

```
[1/3] 搜索
  → 调网易严选搜索API → 拿商品ID+名称列表

[2/3] 抓取详情
  同步版: for循环逐个抓，每个间隔1秒
  协程版: asyncio.gather 并发抓，Semaphore 限流

[3/3] 导出Excel
  → 写 goods_{关键词}.xlsx
  → 列: id / title / image / price_min / subtitle / description
```

## 输出

当前目录生成 Excel 文件：

```
goods_非遗.xlsx
goods_茶具.xlsx
goods_江苏特产.xlsx
```

## 速度对比

| 商品数 | 同步版（串行） | 协程版（并发5） | 协程版（并发10） |
|---|---|---|---|
| 20 | ~40 秒 | ~10 秒 | ~6 秒 |
| 40 | ~80 秒 | ~18 秒 | ~10 秒 |
| 60 | ~120 秒 | ~25 秒 | ~15 秒 |

## 依赖

```bash
pip install httpx openpyxl
```

`httpx` 已包含在项目 `requirements.txt` 中。
