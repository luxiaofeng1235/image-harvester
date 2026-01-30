# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 在此代码库中工作时提供指导。

## 项目概述

Image Harvester 是一个多源图片采集/下载/过滤/归档工具。当前版本只实现了 **Baidu** 数据源。该工具按关键词抓取图片，进行 URL 和内容去重，按分辨率过滤，并组织到基于日期的目录结构中。

## 常用命令

### 运行采集器
```bash
# 基本用法
python -m scripts.run --keywords "猫,狗" --count 50

# 自定义分辨率过滤
python -m scripts.run --keywords "风景" --count 10 --sizes "w>=1200,h>=200"

# 开启调试日志
python -m scripts.run --keywords "风景" --count 10 --debug

# 严格顺序模式（按搜索结果顺序下载，跳过 404）
python -m scripts.run --keywords "风景" --count 10 --strict-order
```

### 添加水印
```bash
# 基本水印（右下角文字）
python -m scripts.stamp --right-text "九界AI"

# 批量打水印（处理整个日期目录下所有分辨率文件夹）
python -m scripts.stamp --in ./data/20260129 --right-text "九界AI" --bold-radius 0

# 自定义输入/输出目录
python -m scripts.stamp --in ./data/20260129/1920-1080 --out ./out --right-text "九界AI"

# 自定义字体和 Logo
python -m scripts.stamp --font ./fonts/custom.ttf --logo ./images/custom.png --right-text "文字"
```

### 测试
```bash
# 运行所有测试
pytest -q

# 运行特定测试文件
pytest tests/test_filters.py -v
```

### 按分辨率整理图片
```bash
# 整理 data/ 根目录的图片到 data/{当前日期}/{宽度-高度}/ 文件夹
python3 organize_by_resolution.py

# 整理 data/20260130/ 目录的图片到 data/20260130/{宽度-高度}/ 文件夹
python3 organize_by_resolution.py --dir data/20260130

# 整理指定目录
python3 organize_by_resolution.py --dir ./images

# 查看帮助
python3 organize_by_resolution.py --help

# 功能说明：
# - 扫描指定目录（不递归子目录）
# - 读取图片分辨率（支持 .jpg, .jpeg, .png, .gif, .bmp, .webp）
# - 智能模式：
#   * data/ 根目录 -> 创建日期子目录 data/{YYYYMMDD}/{分辨率}/
#   * data/20260130/ 子目录 -> 就地整理 data/20260130/{分辨率}/
# - 移动操作（不是复制）
# - 同名文件会被覆盖（Linux/WSL2）
```

## 架构说明

### Pipeline 流程
1. **抓取 URL** (`src/sources/`) - 每个源实现 `ImageSource.fetch_urls(keyword, limit)`
2. **URL 去重** (`src/pipeline/dedupe.py`) - 跟踪已见过的 URL 和内容哈希
3. **下载与探测** (`src/pipeline/downloader.py`) - 使用 HEAD 预检下载，验证图片格式
4. **分辨率过滤** (`src/pipeline/filters.py`) - 应用尺寸规则（精确、比例、范围）
5. **归档** - 保存到 `data/YYYYMMDD/width-height/` 结构
6. **统计** (`src/pipeline/stats.py`) - 每次运行生成 summary.json

### 下载后的目录结构
```
data/
  YYYYMMDD/
    width-height/
      {keyword}_{width}x{height}_{hash}.{ext}
    summary.json
```

### 添加新图片源
1. 在 `src/sources/` 创建新类，继承 `ImageSource`
2. 实现 `fetch_urls(keyword: str, limit: int) -> List[str]`
3. 内部处理分页、限速和重试
4. 在 `config/default.yaml` 的 `sources:` 下注册
5. 在 `tests/` 添加测试（不使用真实网络调用）

### 分辨率过滤规则
支持三种规则类型：
- **精确匹配**：`1300x250` - 精确的宽度和高度
- **比例范围**：`ratio=5.2+/-5%` - 宽高比及容差
- **范围约束**：`w>=1200,h>=200` - 宽度/高度约束，支持运算符（>=, <=, >, <, =）

多个范围条件可以用逗号组合在单个规则中。

### 水印系统 (`scripts/stamp.py`)
- 从 `stamp_input`（默认：`./data`）读取，输出到 `stamp_output`（默认：`./out`）
- 添加 Logo（左上角）和文字（右下角），样式可配置
- 支持发光效果、描边、透明度和自定义字体
- 在输出中保留原始目录结构
- 所有水印设置可通过 `config/default.yaml` 或 CLI 参数配置

### 配置系统
- 基础配置：`config/default.yaml`
- CLI 参数覆盖配置值
- 支持环境变量：`IMG_KEYWORDS`、`IMG_OUT`、`IMG_COUNT` 等
- 配置合并通过 `src/utils/config.py` 实现

### 去重策略
- **URL 去重**：跟踪所有已抓取的 URL，避免重复下载
- **内容哈希去重**：下载内容的 SHA1 哈希（可通过 `hash_algo` 配置）
- **感知哈希**：可选（配置中默认禁用）

### 反爬措施
- 百度源包含 Range 请求预检（0-2047 字节）+ 文件头验证
- 每个源可配置限速（配置中的 `rate_limit`）
- `blocked_domains` 列表跳过特定主机
- `fetch_overage` 倍数在过滤前抓取额外 URL

### 文件命名规范
下载的图片：`{keyword}_{width}x{height}_{hash}.{ext}`
- keyword：已清理（字母数字 + `-_`）
- hash：内容哈希（默认 SHA1）
- ext：从 Content-Type 或 PIL 格式推测

### 重要注意事项
- `organize_by_resolution.py` 脚本是独立工具（不属于主 pipeline）
- 它将图片从 `data/` 根目录移动到 `data/20260129/{分辨率}/` 文件夹
- 在 Linux（WSL2）上，`shutil.move()` 会**覆盖**同名文件
- 水印脚本保留目录结构：`data/20260129/1920-1080/` → `out/20260129/1920-1080/`
- 测试使用模拟响应 - 永远不要在测试中进行真实网络调用

### 合规性
- 数据源可配置且可禁用
- 不绕过验证码、登录或付费墙
- 遵守 `blocked_domains` 配置
- 每个源强制执行限速
