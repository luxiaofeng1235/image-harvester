# 操作文档

本项目用于按关键词抓取百度图片，并按**日期 + 分辨率**归档到目录中。

## 目录结构
下载目录默认在项目根目录的 `./data`：

```
data/YYYYMMDD/width-height/
```

例如：

```
data/20260128/480-272/
data/20260128/1325-146/
```

> 目录名中的分辨率 **来源于图片真实尺寸**，程序先解析图片大小，再按该大小归档。

## 安装依赖
```bash
pip install -r requirements.txt
```

## 基本用法
```bash
python -m scripts.run --keywords "风景" --count 10
```

可选参数示例（放宽分辨率过滤，用于快速验证落盘）：
```bash
python -m scripts.run --keywords "风景" --count 10 --sizes "w>=1,h>=1"
```

## CLI 参数
必填：
- `--keywords` 关键词（逗号分隔）
- `--count` 每个关键词目标下载数量

可选：
- `--sizes` 分辨率规则，可重复；范围规则请作为**单个参数**传入，例如：
  - `--sizes "1300x250"`
  - `--sizes "ratio=5.2+/-5%"`
  - `--sizes "w>=1200,h>=200"`
- `--date` 指定输出日期（格式 `YYYYMMDD`）
- `--sources` 数据源列表（逗号分隔，当前仅 `baidu`）
- `--concurrency` 下载并发
- `--rate-limit` 每源限速（秒）
- `--blocked-domains` 屏蔽域名列表（逗号分隔）
- `--config` 配置文件（默认 `config/default.yaml`）
- `--debug` 打开调试日志（显示抓取与下载细节）
- `--strict-order` 按搜索结果顺序下载（遇到 404/无效自动跳过）

## 配置文件
默认配置：`config/default.yaml`

重点字段：
- `out`: 输出目录（默认 `./out`）
- `count`: 每关键词下载数量
- `sizes` / `size_rules`: 分辨率规则
- `blocked_domains`: 屏蔽域名

## 运行结果
每次运行会生成：
- 日志：`logs/run-YYYYMMDD-HHMMSS.log`
- 汇总统计：`data/YYYYMMDD/summary.json`

## 自动归类校验（可选）
如需确认“目录名分辨率 == 图片真实分辨率”，可执行以下脚本：

```bash
python - <<'PY'
from pathlib import Path
from PIL import Image

root = Path("./data")
for day in root.iterdir():
    if not day.is_dir():
        continue
    for bucket in day.iterdir():
        if not bucket.is_dir():
            continue
        try:
            w, h = map(int, bucket.name.split("-"))
        except Exception:
            print("skip", bucket)
            continue
        for img_path in bucket.iterdir():
            if not img_path.is_file():
                continue
            try:
                with Image.open(img_path) as im:
                    if im.size != (w, h):
                        print("mismatch", img_path, im.size)
            except Exception as e:
                print("error", img_path, e)
PY
```

## 水印剪辑（输出到 out）
```bash
python -m scripts.stamp --right-text "九界AI"
```

默认从 `./data` 读取，输出到 `./out`，并使用 `./images/logo.png` 作为左上角 Logo。
默认字体使用 `./fonts/msyh.ttf`（微软雅黑）。
默认水印距离边缘为 10 像素（可用 `--padding` 覆盖）。
默认文字透明度为 1.0（可用 `--opacity` 调整）。
默认关闭额外加粗（`stamp_bold_radius: 0`），可用 `--bold-radius` 调整。
默认字号比例 `stamp_scale: 0.058`（可用 `--scale` 调整）。
默认文字颜色为偏黄 `#FFD24A`（可用 `--color` 调整）。
默认启用柔光（`stamp_glow_color: #FFE27A`, `stamp_glow_opacity: 0.6`, `stamp_glow_radius: 4`）。
默认底部文字上移 `stamp_bottom_offset: 12`（可用 `--bottom-offset` 调整）。

## 注意事项
- 百度源包含**预检**：Range 0–2047 + 文件头校验 + 反爬过滤，可能导致获取量不足。
- 若数量不足：
  1) 提高 `fetch_overage`（见 `config/default.yaml`）
  2) 换关键词
  3) 临时放宽 `sizes`
