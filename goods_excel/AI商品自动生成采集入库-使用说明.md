# AI商品自动生成采集入库-使用说明

## 1. 文档目的
本说明用于指导 `goods_excel/ai_goods_pipeline/` 的本地安装、配置与运行。

当前实现特点:
- 直接写入 MySQL，不再导出 Excel。
- 当前只维护单表 `jj_wangyi_goods`，不再按天分表，也不新增批次日志表。
- 图片搜索默认只按生成后的商品标题 `title` 搜图，当前主流程仅使用 `百度图片`。
- 百度图片首屏抓取当前依赖 Playwright 渲染后的 DOM。
- Bing 抓取实现和验证脚本仍保留，但主流程默认关闭，可通过 `IMG_ENABLE_BING=1` 恢复。
- 图片候选会额外经过分类感知过滤，优先拦截明显跨城市、跨品类的错图结果。
- 可按需开启 `CLIP` 图片重排，对已通过校验的候选图再做一轮语义排序；当前建议只用于 `128/129`。
- 每条商品必须满足 `1` 张主图 + `3` 张详情图后才允许入库。
- 当前可通过 `OSS_ENABLED=0` 关闭 OSS 上传；关闭后不会再把图片统一转 OSS，而是按归一化后的原图 URL 写库。
- 当前图片有效性校验已提升到“真实图片解码”级别，不再只依赖状态码或响应头。

## 1.1 当前链路速览
- 输入: 命令行传入 `category_id + keywords + count`，并读取根目录 `.env`。
- 生成: `qwen-plus/qwen-max` 按分类 Prompt 生成结构化商品数据。
- 校验: 先做 JSON、分类、价格、字段完整性、标题去重和历史库去重。
- 图片: 固定按 `title` 走百度图片，按浏览器首屏顺序抓取；先做分类感知过滤，再按需做 `CLIP` 重排；如后续打开 `IMG_ENABLE_BING=1`，再追加 Bing 补图。
- 映射: 过滤失效图、离题图、重复图后，固定组装 `1 主图 + 3 详情图`。
- 入库: 满足图片与字段要求后写入 `jj_wangyi_goods`，否则继续补生成。
- 批次: 每条数据会写入 `batch_id/last_batch_id/source_type/source_note`；可手动指定 `--batch-id`，不传则自动使用系统生成批次号。
- 排查: 当前主流程图片问题优先看百度抓取，必要时再单独用 `verify_bing_order.py` 验证 Bing。
- 自检: 可通过 `--check-runtime 1` 快速确认当前图片运行环境，输出是否启用 Bing 及对应渲染状态。

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
- 百度图片首屏顺序抓取当前依赖 Playwright 渲染后的 DOM。
- 若后续需要恢复 Bing 主流程补图，Bing 同样依赖 Playwright 渲染后的 DOM。
- 新环境首次安装后需执行一次 `playwright install chromium`，否则会缺少浏览器内核。

### 4.2 按需安装
如果需要开启 OSS 上传，再安装:
```bash
pip3 install oss2
```

如果需要开启 `CLIP` 图片重排，再安装:
```bash
pip3 install -U transformers huggingface_hub safetensors tokenizers
```

说明:
- 当前 `CLIP` 重排默认关闭，不装也不影响主流程。
- `torch` 需提前可用；有 GPU 可显著降低重排耗时，没有 GPU 也可以用 CPU 跑。
- `CLIP` 只允许读取本地模型目录，默认路径为 `ai_goods_pipeline/runtime/models/chinese-clip-vit-base-patch16`。
- 若本地目录不存在会直接跳过重排，不再回退到 HuggingFace 远端下载。

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
IMG_ENABLE_BING=0
IMG_ENABLE_CLIP_RERANK=0
IMG_CLIP_MODEL=ai_goods_pipeline/runtime/models/chinese-clip-vit-base-patch16
IMG_CLIP_MIN_SCORE=0.22
IMG_CLIP_MAX_CANDIDATES=12
IMG_CLIP_CATEGORY_IDS=128,129

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
- `OSS_ENABLED=0` 表示关闭 OSS。此时标准图片 URL 会按归一化后的结果直接写库，但非标准图片 URL 不会被自动转成统一 OSS 地址。
- `OSS_ENABLED=1` 表示开启 OSS，此时需要补齐 OSS 配置。
- `IMG_ENABLE_CLIP_RERANK=1` 表示开启 `CLIP` 图片重排；默认关闭。
- `IMG_CLIP_MODEL` 只支持本地目录；可填相对项目根目录的路径，也可填绝对路径。
- `IMG_CLIP_CATEGORY_IDS` 当前建议只配置 `128,129`，也就是苏超纪念品和工艺产品。
- `.env` 不应提交到仓库。

## 5.1 单表批次字段
当前所有导入、生成、补录链路都只写入 `jj_wangyi_goods` 一张表，并统一使用以下字段标记批次:
- `batch_id`: 首次入库批次号
- `last_batch_id`: 最近一次处理批次号
- `source_type`: 首次来源类型，当前实际写入值为 `ai_generate / seed_import / legacy_import`
- `source_note`: 来源备注

使用建议:
- 查某次新生成或新导入的数据，看 `batch_id`
- 查最近一次被补图/补描述处理过的数据，看 `last_batch_id`
- 想区分来源入口，看 `source_type`
- 按日期筛选仍使用 `create_time/update_time`
- 异步补录脚本只更新 `last_batch_id`，不会覆盖原始 `batch_id/source_type`

## 6. 当前图片规则
### 6.1 搜图规则
- 当前主流程只使用百度图片搜索，且固定只使用生成后的商品标题 `title`。
- 不再补 `image_keywords`。
- 不再补任务关键词。
- 百度搜索 URL 逻辑等价于:
```text
https://image.baidu.com/search/index?tn=baiduimage&fm=result&ie=utf-8&word=<title>
```
- 如需恢复 Bing 补图，可在 `.env` 中设置 `IMG_ENABLE_BING=1`。

### 6.2 图片筛选规则
- 优先取静态图 `jpg/jpeg/png/webp` 作为主图。
- 详情图固定取后续 `3` 张有效图。
- 明显离题结果、跨城市错图、跨品类错图会被过滤。
- 若开启 `CLIP`，会在“已通过 URL 有效性校验的静态候选图”上做一次语义重排，不会新增图片来源，也不会跳过前面的过滤规则。
- `CLIP` 当前只建议用于 `128/129`；当候选静态图少于 `2` 张、依赖未装好或模型不可用时会自动跳过，不阻塞主流程。
- 只有满足 `1` 主图 + `3` 详情图时才允许入库。
- 图片写库前会先做 URL 归一化。
  - `https://xxx/abc.jpeg?x-tos-process=...` 会裁成 `https://xxx/abc.jpeg`
  - `https://nimg.ws.126.net/?url=http...abc.jpg&thumbnail=...&quality=...` 会裁成 `https://nimg.ws.126.net/?url=http...abc.jpg`
- 采集阶段会对图片字节做一次真实解码，损坏图、伪图片响应、无权限返回页会直接过滤。
- OSS 上传阶段也会再次做真实解码校验，避免把异常内容同步进业务图床。
- 若归一化后已经是标准图片 URL，则主图可直接入库。
- 若归一化后仍不是标准图片 URL，例如 `https://img2.baidu.com/it/u=...` 这类“可打开但前端不易识别”的地址，则在 `OSS_ENABLED=1` 时自动同步 OSS 后再入库。
- `OSS_ENABLED=1` 时，详情图会统一转 OSS 后再写入富文本；主图仍按“标准直链直接写库、非标准图链转 OSS”执行。
- 当前详情图 HTML 输出为裸 `img` 标签，不再使用 `<p><img /></p>` 包裹。

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
  --batch-id suzhou_20260323_a \
  --write-db 1 \
  --dry-run 0
```

### 8.2 农副产品
```bash
python3 ai_goods_pipeline/generate_goods.py \
  --category-id 127 \
  --keywords "江苏农副产品,盐城大米,南通海苔,水产干货" \
  --count 1 \
  --batch-id agri_20260323_a \
  --write-db 1 \
  --dry-run 0
```

### 8.3 苏超纪念品
```bash
python3 ai_goods_pipeline/generate_goods.py \
  --category-id 128 \
  --keywords "苏超纪念品,南京助威围巾,球迷伴手礼" \
  --count 1 \
  --batch-id football_20260323_a \
  --write-db 1 \
  --dry-run 0
```

### 8.4 工艺产品
```bash
python3 ai_goods_pipeline/generate_goods.py \
  --category-id 129 \
  --keywords "江苏工艺产品,宜兴紫砂杯,苏绣团扇,云锦礼品" \
  --count 1 \
  --batch-id craft_20260323_a \
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
- `--batch-id`: 可选，自定义批次号；不传时自动使用系统生成批次号
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

### 11.3 开启 CLIP 图片重排
推荐场景:
- `128 苏超纪念品`：减少“风景图、资讯图、非商品图”混入主图
- `129 工艺产品`：减少“人物上身图、泛场景图、非实物图”排到前面

推荐配置:
```env
IMG_ENABLE_CLIP_RERANK=1
IMG_CLIP_MODEL=/mnt/d/python_work/image-harvester/goods_excel/ai_goods_pipeline/runtime/models/chinese-clip-vit-base-patch16
IMG_CLIP_MIN_SCORE=0.22
IMG_CLIP_MAX_CANDIDATES=12
IMG_CLIP_CATEGORY_IDS=128,129
```

首次手动准备本地模型示例:
```bash
python3 - <<'PY'
from transformers import AutoProcessor, AutoModel

model_name = "OFA-Sys/chinese-clip-vit-base-patch16"
save_dir = "ai_goods_pipeline/runtime/models/chinese-clip-vit-base-patch16"

processor = AutoProcessor.from_pretrained(model_name)
model = AutoModel.from_pretrained(model_name)

processor.save_pretrained(save_dir)
model.save_pretrained(save_dir)
print("saved:", save_dir)
PY
```

说明:
- 这一步只用于首次把模型手动保存到本地目录。
- 项目运行期不会再自动回退远端下载；本地目录不存在时会直接跳过 `CLIP` 重排。

单独评估重排效果:
```bash
python3 ai_goods_pipeline/eval_clip_rerank.py \
  --title '真丝长方丝巾 防晒百搭丝绸配饰' \
  --category-id 129 \
  --query '真丝 长方丝巾 平铺' \
  --count 4 \
  --enable-clip-rerank 1
```

整链路干跑验证:
```bash
IMG_ENABLE_CLIP_RERANK=1 \
IMG_CLIP_MODEL=/mnt/d/python_work/image-harvester/goods_excel/ai_goods_pipeline/runtime/models/chinese-clip-vit-base-patch16 \
python3 ai_goods_pipeline/enrich_seed_goods_from_db.py \
  --category-id 129 \
  --ids 583 \
  --limit 1 \
  --missing-mode none \
  --concurrency 1 \
  --force-image-refresh 1 \
  --dry-run 1
```

维护位置:
- 图片语义词库统一维护在 `ai_goods_pipeline/enums/image_semantics.py`
- 当前同步图片客户端、异步图片客户端、`CLIP` 重排器都从这一处导入，不再各自写死
- 当前 `CLIP` 会优先用百度缩略图做一轮预排，再对前排候选补做原图精排；仍然只在已有候选池内排序，不新增图片来源

### 11.4 种子商品异步补全脚本
适用场景:
- 已经有人工导入的种子商品，仅需从数据库中补 `sub_title / image / description`
- 查询条件固定按 `image` 为空或 `description` 为空筛选
- 适合作为主批量生成链路之外的第二补录方案

脚本路径:
- `goods_excel/ai_goods_pipeline/enrich_seed_goods_from_db.py`

核心参数:
- `--category-id`: 必填，分类 ID，例如 `126/127/128/129`
- `--limit`: 本次最多处理多少条，方便先跑 `1` 条验证
- `--ids`: 指定单条或多条商品 ID，逗号分隔
- `--missing-mode`: `either/image/description/both`
- `--concurrency`: 异步并发数，默认 `3`
- `--dry-run`: `1` 只预览不写库，`0` 正式写库
- `--batch-id`: 可选，自定义本次补录批次号；不传时自动使用系统生成批次号

干跑一条:
```bash
python3 ai_goods_pipeline/enrich_seed_goods_from_db.py \
  --category-id 129 \
  --limit 1 \
  --missing-mode either \
  --concurrency 1 \
  --batch-id enrich_20260323_a \
  --dry-run 1
```

指定 ID 正式写库:
```bash
python3 ai_goods_pipeline/enrich_seed_goods_from_db.py \
  --category-id 129 \
  --ids 571 \
  --limit 1 \
  --missing-mode either \
  --concurrency 1 \
  --dry-run 0
```

说明:
- 当前链路默认仍只使用百度图片，不走 Bing 主流程
- 文案补全与图片抓取均为异步实现；仅当开启 OSS 上传时，OSS SDK 仍通过 `asyncio.to_thread` 包一层同步上传，详情图会统一转 OSS
- 若商品已有主图但缺描述，脚本会保留现有主图，只补详情图与描述
- 正式写库时不会改动原始 `batch_id/source_type`，只更新 `last_batch_id`
- 控制台会输出 `selected/success/updated/failed/log/run_id/summary`

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
- 百度图片搜索页面响应时间
- 图片源站可访问性
- `CLIP` 模型首次加载时间
- OSS 上传是否开启

### 12.4 为什么开了 CLIP 但图片结果看起来没变化
常见原因:
- 当前分类不在 `IMG_CLIP_CATEGORY_IDS` 内
- 有效静态候选图不足 `2` 张
- `IMG_ENABLE_CLIP_RERANK=0`
- `IMG_CLIP_MODEL` 未指向有效模型目录
- 当前错图问题出在“候选池本身就没找到对图”，这种情况 `CLIP` 只能重排已有候选，不能凭空补图

## 13. 推荐排查顺序
出现问题时建议按这个顺序排查:
1. 先看 `.env` 是否正确
2. 再看数据库连通性
3. 再看千问接口是否可用
4. 再看百度图片搜索是否可访问
5. 如任务变慢，先关闭 `OSS_ENABLED`
6. 最后查看 `ai_goods_pipeline/logs/` 下日志
