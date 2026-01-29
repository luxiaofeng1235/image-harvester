# Image Harvester (Baidu only for now)

多源图片采集/下载/过滤/归档工具。当前版本只实现了 **Baidu** 数据源，其他源可按同样接口扩展。

## 功能
- 多关键词抓取 → URL 去重 → 下载 → 分辨率过滤 → 归档
- 输出目录结构：`out/YYYYMMDD/width-height/`
- 文件命名：`{keyword}_{width}x{height}_{hash}.{ext}`
- 失败重试、限速、日志、summary 统计

## 快速开始
```bash
python -m scripts.run --keywords "猫,狗" --count 50
```

默认下载输出到 `./data`。

## CLI 参数
必填：
- `--keywords` 关键词（逗号分隔）
- `--out` 输出目录
- `--count` 每个关键词目标下载量

可选：
- `--sizes` 分辨率规则，可重复；范围规则请作为单个参数，例如 `--sizes "w>=1200,h>=200"`
- `--date` 输出日期（YYYYMMDD）
- `--sources` 数据源列表（逗号分隔，当前仅 `baidu`）
- `--concurrency` 下载并发
- `--rate-limit` 每源限速（秒）
- `--blocked-domains` 屏蔽域名列表（逗号分隔）
- `--strict-order` 按搜索结果顺序下载（遇到 404/无效自动跳过）

## 水印剪辑（输出到 out）
```bash
python -m scripts.stamp --left-text "胡" --right-text "苏州九界\\n九界AI"
```

默认从 `./data` 读取，输出到 `./out`，并使用 `./images/logo.png` 作为左上角 Logo。

## 分辨率规则示例
- 精确匹配：`1300x250`
- 比例范围：`ratio=5.2+/-5%`
- 宽高范围：`w>=1200,h>=200`

## 配置
默认配置在 `config/default.yaml`，可用 `--config` 指定。
环境变量可覆盖（简单模式）：
- `IMG_KEYWORDS`, `IMG_OUT`, `IMG_COUNT`, `IMG_SOURCES`, `IMG_CONCURRENCY`, `IMG_RATE_LIMIT`, `IMG_SIZES`, `IMG_DATE`, `IMG_BLOCKED_DOMAINS`

## 测试
```bash
pytest -q
```

## 目录结构
- `src/` 业务代码
- `config/` 配置
- `data/` 输出
- `logs/` 日志
- `scripts/` CLI
- `tests/` 单测
