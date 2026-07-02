# 网易严选商品采集工具

**目录**: `goods_excel/fetch_details.py`

协程并发版，默认 5 个商品同时抓取，速度比串行快 3~5 倍。

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

## 流程

```
[1/3] 搜索
  → 调网易严选搜索API → 拿商品ID+名称列表

[2/3] 并发抓取详情
  → asyncio.gather 并发抓，Semaphore 限流

[3/3] 导出Excel
  → 写 goods_{关键词}.xlsx
  → 列: id / title / image / price_min / subtitle / description
```

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
