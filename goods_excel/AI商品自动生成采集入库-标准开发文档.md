# AI商品自动生成采集入库-标准开发文档

## 1. 文档信息
- 文档版本: `v1.0`
- 创建日期: `2026-03-04`
- 适用项目: `image-harvester/goods_excel`
- 目标系统: `jiujie_shop.jj_wangyi_goods`

## 2. 背景与目标
当前历史采集数据规模有限、颗粒度不足。目标是建设一套可持续运行的数据生产程序，按分类自动生成更细化的商品数据，并自动补齐图片后落库。

核心目标:
- 支持按 `category_id + 关键词 + 数量` 生成商品。
- 使用千问模型生成结构化商品文案与价格。
- 使用图片接口抓取图片并映射主图/详情图。
- 落地到 MySQL 表 `jj_wangyi_goods`。
- 结果可控: 价格区间、地域覆盖、去重、合规校验。

## 3. 范围与非范围
### 3.1 范围内
- AI 结构化商品数据生成。
- 图片接口抓取与商品图映射。
- 数据校验、重试、入库。
- 可选 Excel 导出与审稿模式。

### 3.2 范围外
- 前台商城 UI 改造。
- 商品上架审核工作流系统化开发。
- 支付、库存、订单模块。

## 4. 业务约束
### 4.1 分类映射
| category_id | 分类名称 | 说明 |
|---|---|---|
| 126 | 江苏特产 | 低中客单为主，强调本地特产与礼赠 |
| 127 | 非遗 | 工艺与文化属性，允许中高客单 |
| 128 | AI科技 | 以服务/方案型商品为主 |
| 129 | 苏超纪念品 | 文创周边，严控高价 |

### 4.2 本地化要求
- 默认全部商品都与江苏本土文化/产业相关。
- 生成批次尽量覆盖江苏 13 市:
  - 南京、无锡、徐州、常州、苏州、南通、连云港、淮安、盐城、扬州、镇江、泰州、宿迁。

### 4.3 价格风控要求
- 126 江苏特产: 建议 `19.90 ~ 399.00`，少量高端礼盒可到 `899.00`。
- 127 非遗: 建议 `59.00 ~ 699.00`，少量收藏可到 `1999.00`。
- 128 AI科技: 建议 `299.00 ~ 1000000.00`，价格需和交付范围匹配。
- 129 苏超纪念品: 建议 `5.90 ~ 99.00`，少量礼盒可到 `299.00`。

## 5. 总体架构
```
输入参数(category_id/keywords/count)
        |
        v
Prompt组装(全局+分类+任务+输出Schema)
        |
        v
千问API生成结构化商品(JSON)
        |
        v
规则校验(字段/价格/去重/地域/合规)
        |
        +--不通过--> 重试或丢弃
        |
        v
图片接口抓取(getImages?key=...)
        |
        v
主图+详情图映射(description拼图文HTML)
        |
        v
写入MySQL(jj_wangyi_goods)
        |
        v
日志与报表(成功/失败/重试原因)
```

## 6. 外部接口定义
### 6.1 千问接口
- URL: `https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions`
- 方法: `POST`
- 鉴权: `Authorization: Bearer ${QW_KEY}`
- 模型策略:
  - 默认: `qwen-plus` (性价比高)
  - 深度场景: `qwen-max` (复杂生成/重写)

请求最小结构:
```json
{
  "model": "qwen-plus",
  "messages": [
    {"role": "system", "content": "系统提示词"},
    {"role": "user", "content": "任务提示词"}
  ],
  "temperature": 0.7
}
```

### 6.2 图片接口
- URL: `https://ptapi.jsss999.com/api/fetch/getImages?key=<关键词>`
- 方法: `GET`
- 返回示例:
```json
{
  "code": 1,
  "msg": "获取成功",
  "data": [
    "https://.../1.jpg",
    "https://.../2.jpg"
  ]
}
```

## 7. 数据契约与字段映射
### 7.1 AI输出契约(JSON数组)
每个对象最少字段:
- `title` (string)
- `subtitle` (string)
- `price` (number/string，可转 decimal)
- `selling_points` (array[string] 或 string)
- `attrs` (object 或 array)
- `image_keywords` (array[string]，用于图片搜索，允许为空)

### 7.2 数据库映射
目标表: `jiujie_shop.jj_wangyi_goods`

| 目标字段 | 来源 | 规则 |
|---|---|---|
| `goods_name` | `title` | 必填，去重后写入 |
| `sub_title` | `subtitle` | 可为空 |
| `category_id` | 任务入参 | 必填 |
| `image` | 图片接口 `data[0]` | 必填，失败则重试/跳过 |
| `price` | `price` | 转 `decimal(10,2)` |
| `description` | 文案+详情图 | HTML 拼接 |
| `en_name` | 可选 | 可留空 |
| `create_time` | 系统时间 | 自动写入 |
| `update_time` | 系统时间 | 自动写入 |

### 7.3 description 拼接模板
```html
<div class="product-description">
  <p><strong>商品亮点</strong>：{{selling_points_text}}</p>
  <p><strong>规格属性</strong>：{{attrs_text}}</p>
</div>
<div class="product-detail">
  <p><img src="{{detail_img_1}}" /></p>
  <p><img src="{{detail_img_2}}" /></p>
  <p><img src="{{detail_img_3}}" /></p>
</div>
```

## 8. Prompt工程标准
### 8.1 组装结构
- `system_prompt`: 全局角色与硬规则
- `category_profile`: 分类个性化规则
- `task_prompt`: 当前任务输入(关键词/数量/城市池)
- `output_schema`: 强制 JSON 字段定义
- `self_check_prompt`: 去重与合规自检

### 8.2 system_prompt 约束
- 角色: 电商商品策划助手。
- 仅输出 JSON，禁止额外说明。
- 禁止输出外链、联系方式、夸大承诺、违规内容。
- 强调江苏本地化语境。

### 8.3 分类个性化策略
- 126/129: 强约束价格，禁止夸高。
- 128: 服务型商品可高客单，但必须交付范围明确。
- 127: 工艺和材质信息必须可解释。

## 9. 校验与容错
### 9.1 强制校验
- 字段完整性校验: 缺核心字段即失败。
- 价格校验: 不在分类范围内则重试。
- 去重校验:
  - 与本批次 title 去重。
  - 与库内近似标题去重(建议相似度阈值 `>0.88` 拦截)。
- 地域校验: 批次内城市分布不能过于集中。

### 9.2 图片校验
- URL 去重。
- HEAD/GET 可访问且状态码 `200`。
- `Content-Type` 为图片。
- 长度建议 `>1KB`。

### 9.3 重试策略
- 千问接口: 最多 `3` 次，指数退避 `1s/2s/4s`。
- 图片接口: 最多 `3` 次，指数退避 `1s/2s/4s`。
- 单条商品最大处理次数: `2` 轮，超限入失败队列。

## 10. 配置规范(.env)
建议配置项:
```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=root
DB_NAME=jiujie_shop
DB_TABLE=jj_wangyi_goods

QW_OPEN_URL=https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
QW_KEY=your_key_here
QW_MODEL_DEFAULT=qwen-plus
QW_MODEL_DEEP=qwen-max
QW_TEMPERATURE=0.7
QW_MAX_TOKENS=4096
QW_SYSTEM_PROMPT=你是电商商品策划助手...

IMG_API_URL=https://ptapi.jsss999.com/api/fetch/getImages
IMG_TIMEOUT=20
IMG_RETRY=3
```

说明:
- `.env` 禁止入库，保留 `.env.example`。
- 已泄露旧 key 需尽快轮换。

## 11. 建议代码结构
`goods_excel/` 下新增:
- `generate_goods.py` 主入口
- `pipeline.py` 编排流程
- `clients/qwen_client.py`
- `clients/image_client.py`
- `validators/goods_validator.py`
- `writers/db_writer.py`
- `writers/excel_writer.py` (可选)
- `prompts/category_profiles.py`
- `utils/retry.py`, `utils/logger.py`

## 12. 运行方式
示例:
```bash
python3 generate_goods.py \
  --category-id 126 \
  --keywords "江苏特产,盐城特产,地方礼盒" \
  --count 50 \
  --model qwen-plus \
  --write-db 1
```

可选参数:
- `--dry-run 1` 仅生成不入库
- `--export-excel 1` 导出审稿文件
- `--city-strategy balanced` 按13市均衡分布

## 13. 测试与验收
### 13.1 功能验收
- 能按分类稳定生成指定数量商品。
- 每条商品至少 1 张主图，建议 3 张以上详情图。
- 数据成功写入 `jj_wangyi_goods`。

### 13.2 质量验收
- 126/129 不出现明显高价离谱数据。
- 128 商品文案体现服务交付，不是快消品描述。
- 同批重复标题率低于 `2%`。
- 江苏地域分布不集中于 1-2 个城市。

### 13.3 稳定性验收
- 100 条批处理成功率 >= `95%`。
- 失败数据可追踪原因并可重试。

## 14. 日志与监控
- 日志级别: `INFO/WARN/ERROR`
- 关键指标:
  - 生成总数、成功数、失败数
  - 千问请求次数/失败次数
  - 图片请求次数/失败次数
  - 平均单条耗时
- 输出建议:
  - 控制台摘要
  - `logs/run_YYYYMMDD_HHMMSS.log`
  - `logs/failures_*.jsonl`

## 15. 风险与应对
- 风险: 模型返回非 JSON。
  - 应对: JSON schema 校验 + 自动重试 + 修复器。
- 风险: 价格漂移不合理。
  - 应对: 分类价带硬校验，超限直接拦截。
- 风险: 图片失效。
  - 应对: URL 校验 + 失败重试 + 备用关键词。
- 风险: 密钥泄露。
  - 应对: key 轮换、最小权限、配置隔离。

## 16. 里程碑建议
- M1: 打通端到端(生成->图片->入库)。
- M2: 加入严格校验与失败重试。
- M3: 加入分类精细 Prompt 与城市均衡策略。
- M4: 批量运行与质量报表。

---
该文档作为后续 Python 实现与联调的唯一基线。若需求变更，需同步更新版本号与变更记录。
