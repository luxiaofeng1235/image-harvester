# WordPress 产品数据同步方案

## Context

本地数据库导出了 75 条产品数据（`zgz_products_import.csv`），需要批量同步到线上 WordPress 站点（`https://www.zgzonre.com`），避免手动逐条发布文章。通过 WordPress REST API 实现自动化同步。

## 数据源

文件：`zgz_products_import.csv`（GBK 编码，75 条记录）

CSV 字段：
| 字段 | 说明 | 示例 |
|------|------|------|
| product_id | 产品ID | 152 |
| title | 产品标题 | 风道加热器 |
| oss_image_url | 图片URL，多个用`\|`分隔 | https://static.jsss999.com/uploads/files/xxx.jpg\|... |
| category_path | 分类路径，`->`分隔 | 加热器->风道加热器系列产品 |
| content_html | 产品详情HTML | `<div>...</div>` |

## 线上分类（已创建完成）

### 一级分类

| ID | 名称 | slug |
|----|------|------|
| 37 | 加热器系列产品 | heater |
| 38 | 搅拌设备系列产品 | mixing-equipment |
| 39 | 水处理系列产品 | water-treatment-equipment |

### 二级分类（已创建）

| ID | 名称 | slug | 父分类ID |
|----|------|------|----------|
| 42 | 导热油加热器 | thermal-oil-heater | 37 |
| 43 | 管道加热器 | pipeline-heater | 37 |
| 44 | 风道加热器 | duct-heater | 37 |
| 45 | 电加热器 | electric-heater-series | 37 |
| 46 | 电加热元件 | electric-heating-tube | 37 |
| 47 | 搅拌罐 | mixing-tank | 38 |
| 48 | 搅拌器 | agitator | 38 |
| 49 | 过滤器 | mechanical-filter | 39 |
| 50 | 除污器 | strainer | 39 |
| 51 | 分集水器 | manifold | 39 |

## CSV 分类 → WP 分类 ID 映射

| CSV category_path | WP 分类 ID | 产品数 |
|---|---|---|
| 加热器->导热油加热器 | 42 | 15 |
| 加热器->管道加热器系列产品 | 43 | 5 |
| 加热器->风道加热器系列产品 | 44 | 4 |
| 加热器->电加热器系列产品 | 45 | 16 |
| 加热器->电加热元件系列产品 | 46 | 6 |
| 搅拌设备->搅拌罐系列产品 | 47 | 7 |
| 搅拌设备->搅拌器系列产品 | 48 | 8 |
| 水处理设备->过滤器系列产品 | 49 | 6 |
| 水处理设备->除污器系列产品 | 50 | 6 |
| 水处理设备->分集水器系列产品 | 51 | 2 |

## 技术方案

### 使用 WordPress REST API + Python 脚本

**认证方式：** Application Password（WordPress 后台 → 用户 → 个人资料 → 应用程序密码）

**API 端点：**
- `POST /wp-json/wp/v2/media` - 上传图片
- `POST /wp-json/wp/v2/posts` - 创建文章
- `GET /wp-json/wp/v2/categories` - 查询分类

### CSV 字段 → WP API 字段对应

| CSV 字段 | WP API 字段 | 说明 |
|---|---|---|
| title | title | 直接传 |
| content_html | content | HTML 内容直接传 |
| category_path | categories | 映射为 WP 分类 ID 数组，如 `[42]` |
| oss_image_url 第一张 | featured_media | 先上传到媒体库拿到 media_id |

### 同步流程

```
遍历 CSV 逐条同步文章：
  ├── 1. 去重检查（product_id + category_path）
  │     └── 已同步则跳过
  │
  ├── 2. 上传特色图片
  │     ├── 取 oss_image_url 的第一张图片
  │     ├── 下载图片
  │     ├── POST /wp-json/wp/v2/media 上传到 WordPress 媒体库
  │     └── 拿到 media_id
  │
  └── 3. 创建文章
        ├── POST /wp-json/wp/v2/posts
        ├── title = 产品标题
        ├── content = content_html（已处理好的 HTML）
        ├── status = 'draft' 或 'publish'
        ├── categories = [二级分类ID]
        ├── tags = [中热ID, 一级分类标签ID]
        └── featured_media = media_id
```

### 脚本文件

脚本：`html/zgznore/sync_to_wp.py`

**配置项（脚本顶部）：**
```python
WP_URL = 'https://www.zgzonre.com/wp-json/wp/v2'
WP_USER = 'jiujie'                    # WordPress 登录用户名
WP_APP_PASSWORD = 'xxxx xxxx xxxx'    # Application Password
CSV_FILE = 'zgz_products_import.csv'
POST_STATUS = 'draft'                 # draft=草稿, publish=直接发布
```

**依赖：** Python 3 + requests
```bash
pip install requests
```

### 使用方法

```bash
# 单条测试（草稿模式）
python3 html/zgznore/sync_to_wp.py --id 152

# 单条直接发布
python3 html/zgznore/sync_to_wp.py --id 152 --publish

# 强制重跑某条（忽略去重）
python3 html/zgznore/sync_to_wp.py --id 152 --force

# 批量同步全部（草稿）
python3 html/zgznore/sync_to_wp.py

# 批量同步全部（直接发布）
python3 html/zgznore/sync_to_wp.py --publish
```

参数说明：
- `--id <product_id>`：只同步指定 product_id 的那条产品
- `--force`：忽略去重记录，强制重新同步
- `--publish`：直接发布（默认草稿模式）

### 标签映射

每篇文章自动打两个标签：**中热**（统一） + **一级分类标签**

| 标签 | ID | 适用分类 |
|---|---|---|
| 中热 | 40 | 所有产品 |
| 加热器 | 63 | 加热器->* |
| 搅拌设备 | 64 | 搅拌设备->* |
| 水处理设备 | 65 | 水处理设备->* |

### 防重复机制

- 去重 key：`product_id + category_path`
- 已同步记录保存在 `sync_progress.json`
- 每次运行自动跳过已同步的产品
- 支持断点续传：中断后重跑会从上次位置继续
- 使用 `--force` 可忽略去重强制重新同步

### 输出文件

- `sync_result.log`：同步日志（成功/失败记录）
- `sync_progress.json`：已同步进度（用于去重和断点续传）

### 容错

- 图片上传失败不阻断，文章仍然创建（无特色图片）
- 每条之间间隔 1 秒，避免触发服务器限制

### 注意事项

1. **先用 draft 模式测试**，确认没问题再加 `--publish` 参数
2. **正文图片保持远程 URL**（`static.jsss999.com`），只有特色图片上传到 WP 媒体库
3. **服务器宝塔面板拦截 DELETE 请求**，删除文章需在 WP 后台手动操作

## 执行步骤

1. 在 WordPress 后台生成 Application Password
2. 将用户名和密码填入脚本配置
3. 用 `--id` 参数先跑单条测试（草稿模式）
4. 到后台检查文章内容、分类、标签、特色图片是否正确
5. 确认无误后，加 `--publish` 批量同步全部

## 验证方式

- 后台查看文章列表，确认标题、分类正确
- 确认标签显示正确（中热 + 一级分类标签）
- 打开文章详情页，确认正文内容和图片显示正常
- 确认特色图片已设置
- 检查分类页面，确认文章归类正确
