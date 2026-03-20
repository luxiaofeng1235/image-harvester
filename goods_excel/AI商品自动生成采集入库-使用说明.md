# AI商品自动生成采集入库-使用说明

## 1. 文档目的
本说明用于指导 `goods_excel/ai_goods_pipeline/` 的本地安装、配置与运行。

当前实现特点:
- 直接写入 MySQL，不再导出 Excel。
- 图片搜索默认只按生成后的商品标题 `title` 搜图，当前顺序为 `百度图片 -> Bing 图片`。
- 百度图片和 Bing 图片首屏抓取当前都依赖 Playwright 渲染后的 DOM。
- 图片候选会额外经过分类感知过滤，优先拦截明显跨城市、跨品类的错图结果。
- 每条商品必须满足 `1` 张主图 + `3` 张详情图后才允许入库。
- 当前可通过 `OSS_ENABLED=0` 关闭 OSS 上传，直接写入原图 URL。

## 1.1 当前链路速览
- 输入: 命令行传入 `category_id + keywords + count`，并读取根目录 `.env`。
- 生成: `qwen-plus/qwen-max` 按分类 Prompt 生成结构化商品数据。
- 校验: 先做 JSON、分类、价格、字段完整性、标题去重和历史库去重。
- 图片: 固定按 `title` 走 `百度图片 -> Bing 图片`，按浏览器首屏顺序抓取。
- 映射: 过滤失效图、离题图、重复图后，固定组装 `1 主图 + 3 详情图`。
- 入库: 满足图片与字段要求后写入 `jj_wangyi_goods`，否则继续补生成。
- 排查: 首屏顺序问题优先用 `verify_baidu_order.py` 或 `verify_bing_order.py` 单独验证。
- 自检: 可通过 `--check-runtime 1` 快速确认百度/Bing 的 Playwright 渲染能力。

## 2. 代码位置
- 主目录: `goods_excel/ai_goods_pipeline/`
- 启动脚本: `goods_excel/ai_goods_pipeline/generate_goods.py`
- 主开发文档: `goods_excel/AI商品自动生成采集入库-标准开发文档.md`

## 3. 运行环境
- Python: `3.10+`
- 推荐: `Python 3.12`
- MySQL: `5.7+` 或 `8.0+`
- 操作系统: Linux / macOS / Windows 均可

## 4. 依赖安装
### 4.1 必装依赖
```bash
pip3 install -r requirements.txt
playwright install chromium
```

如需手动安装，等价命令为:
```bash
pip3 install requests lxml PyMySQL python-dotenv playwright
```

说明:
- 百度图片与 Bing 图片首屏顺序抓取当前都依赖 Playwright 渲染后的 DOM。
- 新环境首次安装后需执行一次 `playwright install chromium`，否则会缺少浏览器内核。

### 4.2 按需安装
如果需要开启 OSS 上传，再安装:
```bash
pip3 install oss2
```

### 4.3 当前代码未使用的库
- `rapidfuzz` 当前代码没有实际引用，不属于必装依赖。

## 5. 配置文件
项目使用根目录下的 `.env`:
```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=jiujie_shop
DB_PASSWORD=your_password
DB_NAME=jiujie_shop
DB_CHARSET=utf8mb4
DB_TABLE=jj_wangyi_goods
TARGET_TABLE=jj_wangyi_goods

QW_OPEN_URL=https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
QW_KEY=your_qwen_key
QWEN_KEY=your_qwen_key
QW_MODEL_DEFAULT=qwen-plus
QW_MODEL_DEEP=qwen-max
QW_TEMPERATURE=0.7
QW_MAX_TOKENS=4096
QW_BATCH_SIZE=15
QW_SYSTEM_PROMPT=你是资深电商商品策划与文案助手。仅返回 JSON 数组。

IMG_TIMEOUT=20
IMG_RETRY=3
IMG_MIN_BYTES=1024
IMG_ALLOW_GIF_AS_MAIN=0

TITLE_SIMILARITY_THRESHOLD=0.88
TASK_MAX_ATTEMPTS_MULTIPLIER=3

OSS_ENABLED=0
OSS_ACCESS_KEY_ID=
OSS_ACCESS_KEY_SECRET=
OSS_BUCKET=
OSS_ENDPOINT=
OSS_VIEW_DOMAIN=
```

说明:
- `OSS_ENABLED=0` 表示关闭 OSS，直接写原始图片 URL。
- `OSS_ENABLED=1` 表示开启 OSS，此时需要补齐 OSS 配置。
- `.env` 不应提交到仓库。

## 6. 当前图片规则
### 6.1 搜图规则
- Bing 搜索固定只使用生成后的商品标题 `title`。
- 不再补 `image_keywords`。
- 不再补任务关键词。
- 搜索 URL 逻辑等价于:
```text
https://cn.bing.com/images/search?q=<title>&qft=+filterui:imagesize-large&form=IRFLTR&first=1
```

### 6.2 图片筛选规则
- 优先取静态图 `jpg/jpeg/png/webp` 作为主图。
- 详情图固定取后续 `3` 张有效图。
- 明显离题的 Bing 结果会被过滤，例如军事、演习、武器相关文本结果。
- 只有满足 `1` 主图 + `3` 详情图时才允许入库。

## 7. 模型策略
- 主模型: `qwen-plus`
- 回退模型: `qwen-max`

建议:
- 批量生成默认用 `qwen-plus`
- 遇到复杂商品、JSON 不稳、描述质量不够时再切 `qwen-max`

## 8. 启动方式
在 `goods_excel/` 目录下执行:

### 8.1 苏州特产
```bash
python3 ai_goods_pipeline/generate_goods.py \
  --category-id 126 \
  --keywords "苏州特产,苏州碧螺春,苏式糕点,阳澄湖伴手礼" \
  --count 1 \
  --write-db 1 \
  --dry-run 0
```

### 8.2 农副产品
```bash
python3 ai_goods_pipeline/generate_goods.py \
  --category-id 127 \
  --keywords "江苏农副产品,盐城大米,南通海苔,水产干货" \
  --count 1 \
  --write-db 1 \
  --dry-run 0
```

### 8.3 苏超纪念品
```bash
python3 ai_goods_pipeline/generate_goods.py \
  --category-id 128 \
  --keywords "苏超纪念品,南京助威围巾,球迷伴手礼" \
  --count 1 \
  --write-db 1 \
  --dry-run 0
```

### 8.4 工艺产品
```bash
python3 ai_goods_pipeline/generate_goods.py \
  --category-id 129 \
  --keywords "江苏工艺产品,宜兴紫砂杯,苏绣团扇,云锦礼品" \
  --count 1 \
  --write-db 1 \
  --dry-run 0
```

## 9. 参数说明
- `--category-id`: 分类 ID，当前支持 `126/127/128/129`
- `--keywords`: 任务关键词，主要用于控制生成方向，不再用于 Bing 搜图
- `--count`: 最终成功入库数量
- `--model`: 指定主模型，默认按分类配置
- `--fallback-model`: 指定回退模型
- `--write-db`: `1` 写库，`0` 不写库
- `--dry-run`: `1` 只跑流程不写库，`0` 正式写库
- `--export-excel`: 当前保留参数，但 DB-first 实现下不使用
- `--city-strategy`: 城市分布策略，默认 `balanced`
- `--check-runtime`: 只做图片运行环境自检，不生成、不入库

自检示例:
```bash
python3 ai_goods_pipeline/generate_goods.py --check-runtime 1
```

## 10. 结果输出
成功执行后，控制台会输出:
- `run_id`
- 请求数量 `requested`
- 成功数量 `success`
- 入库数量 `inserted`
- 失败数量 `failures`
- 运行日志路径 `log`
- 失败日志路径 `failures_log`
- 质量报表路径 `report`
- 质量报表摘要 `quality_report`

日志目录:
- `goods_excel/ai_goods_pipeline/logs/`

质量报表文件:
- `goods_excel/ai_goods_pipeline/logs/report_*.json`

当前质量报表默认包含:
- 成功率 `success_rate`
- 失败原因分布 `failure_reason_distribution`
- 图片来源分布 `image_source_distribution`
- 搜图来源分布 `search_source_distribution`
- 平均耗时 `avg_duration_per_success_seconds`
- 平均候选处理耗时 `avg_candidate_processing_seconds`

## 11. 常见开关
### 11.1 关闭 OSS 上传
```env
OSS_ENABLED=0
```

### 11.2 开启 OSS 上传
```env
OSS_ENABLED=1
```

并补齐:
- `OSS_ACCESS_KEY_ID`
- `OSS_ACCESS_KEY_SECRET`
- `OSS_BUCKET`
- `OSS_ENDPOINT`
- `OSS_VIEW_DOMAIN`

## 12. 常见问题
### 12.1 为什么商品生成了但没有入库
常见原因:
- 标题和库内历史数据重复或高度相似
- 图片不足 `4` 张
- 主图无效
- 模型返回结构不符合要求

### 12.2 为什么图片不准确
当前已经收紧为只按 `title` 搜图，但仍可能出现同名异义词问题。若某些品类歧义较大，应优先优化生成标题本身，而不是再补搜图关键词。

### 12.3 为什么运行时间忽快忽慢
主要受以下外部链路影响:
- 千问接口响应时间
- Bing 图片搜索页面响应时间
- 图片源站可访问性
- OSS 上传是否开启

## 13. 推荐排查顺序
出现问题时建议按这个顺序排查:
1. 先看 `.env` 是否正确
2. 再看数据库连通性
3. 再看千问接口是否可用
4. 再看 Bing 图片搜索是否可访问
5. 如任务变慢，先关闭 `OSS_ENABLED`
6. 最后查看 `ai_goods_pipeline/logs/` 下日志
