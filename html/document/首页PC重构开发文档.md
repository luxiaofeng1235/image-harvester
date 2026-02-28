# 首页 PC 重构开发文档

## 0. 开发原型参考
1. 开发原型图：`document/page148-full-wide.png`
2. 请以该图作为首页 PC 重构的主参考（视觉结构、区块顺序、间距比例）。
3. 本文档已有约束仍然有效：首页最上侧 Banner 与底部 Footer 不在本次开发范围内。

## 1. 项目目标
基于提供的页面截图，重构一个 PC 端企业官网首页。要求在视觉结构上与原页面一致，代码结构可维护，并支持接口驱动渲染。

核心目标：
1. 保持原页面信息架构：顶部导航、产品模块、应用范围（顶部 Banner 与底部页脚本阶段不开发）。
2. 中间内容改为接口渲染（产品、应用范围、文案等）。
3. 首页采用“分类驱动”模式：切换大分类后，仅刷新上半部分与中间产品区数据。
4. Banner 左侧分类切换：不同分类加载不同 Banner 图集。

## 2. 范围与约束

### 2.1 本次范围
1. 仅 PC 页面（建议设计宽度 1200px 内容区，最小支持 1366 宽屏）。
2. 首页单页面重构（同一页面内动态切换分类数据，不拆分多个分类页面）。
3. 前端接口联调与容错处理。
4. 基础交互与样式还原。
5. 明确排除：首页最上侧 Banner 与底部 Footer 不在本次开发范围内。

### 2.2 非本次范围
1. 后台管理系统。
2. 移动端适配。
3. 登录/权限体系。
4. SEO 深度优化（仅保留基础 meta 结构即可）。
5. 首页最上侧 Banner 区开发。
6. 首页底部 Footer 区开发。

## 2.3 技术栈与实现约定
1. 页面技术：`HTML5 + CSS3 + 原生 JavaScript (ES6+)`。
2. 数据请求：使用 `fetch` 调用 WordPress REST API（`wp-json/wp/v2/posts`）。
3. 异步翻页：使用原生 JS 实现（非 jQuery）。
4. 并发控制：使用 `AbortController` 取消上一次列表请求，避免连点分页导致数据乱序。
5. 分页依据：解析响应头 `X-WP-Total`、`X-WP-TotalPages` 驱动分页器。
6. 依赖策略：业务逻辑不依赖 jQuery，避免与站点现有 jQuery/Migrate 产生冲突。
7. 可视组件：轮播可使用现有 `Swiper`（仅组件层依赖，不绑定 jQuery）。
8. 配置来源：分类、子分类、文案与图片优先读取 `document/home-category-content-config.json`。

## 2.4 文件组织与发布约定
1. 禁止在同一个 HTML 文件内大量混写样式和业务脚本（仅允许极少量必要初始化代码）。
2. 页面结构、样式、脚本必须拆分：
   - `category.html`（页面结构，若历史命名使用 `categoryies.html` 也可）
   - `assets/css/category.css`（样式）
   - `assets/js/category-page.js`（页面初始化、URL 参数、事件绑定）
   - `assets/js/category-api.js`（接口请求、AbortController、分页头解析）
   - `assets/js/category-render.js`（列表/分页/状态渲染）
   - `home-category-content-config.json`（分类与文案配置）
3. 业务代码独立封装，避免把请求、渲染、事件处理散落在内联脚本中。
4. 产物需支持同步到 OSS 后被 WordPress 直接引用（`<link>` / `<script src>`）。
5. WP 页面仅做容器与资源引入，不承载复杂业务代码，便于后续版本迭代与回滚。

## 3. 页面信息架构
从上到下分为 6 个区块（其中第 2 和第 6 区块本阶段不开发）：
1. 顶部导航区（深色背景）
2. Banner 区（左侧分类 + 右侧大图轮播）
3. 产品主展示区（标题、主图、简介）
4. 产品列表区（卡片网格）
5. 应用范围区（图片列表）
6. 页脚区（关于我们、联系我们、栏目链接、备案）

## 4. 模块详细说明

## 4.1 顶部导航区
1. 固定在页面顶部（可选：滚动后吸顶）。
2. 菜单项示例：`首页 / 加热器 / 搅拌设备 / 水处理设备 / AI平台 / 联系我们`。
3. 当前页高亮：`首页`。
4. 鼠标悬停提供颜色变化。

数据来源：
1. 可先静态配置。
2. 如后续有导航接口，改为接口渲染。

## 4.2 Banner 区（重点）

### 4.2.1 结构
1. 左侧分类菜单（纵向）：
   - 加热器
   - 搅拌设备（若业务文案是“脚本设备”，以后端返回为准）
   - 水处理设备
2. 右侧 Banner 图轮播区。
3. 轮播支持左右切换箭头、分页点、自动播放。

### 4.2.2 交互规则
1. 页面首次进入默认选中第一个分类（加热器），加载该分类图片集。
2. 点击左侧分类时：
   - 更新当前分类高亮。
   - 请求该分类 Banner 数据。
   - 请求该分类产品主展示、产品列表数据。
   - 重置轮播到第一张，产品分页回到第 1 页。
3. 切换分类时需要防抖（200ms）避免频繁请求。
4. 请求失败时：
   - 保留上一次成功数据。
   - 右上角或控制台输出错误日志。
   - 可显示“加载失败，请重试”。

### 4.2.3 Banner 数据结构（建议）
```json
{
  "categoryKey": "heater",
  "categoryName": "加热器",
  "banners": [
    {
      "id": 101,
      "imageUrl": "https://xxx/banner1.jpg",
      "title": "",
      "subTitle": "",
      "linkUrl": "/product/101",
      "sort": 1
    }
  ]
}
```

### 4.2.4 分类 key 约定
1. `heater` -> 加热器
2. `mixer` -> 搅拌设备（或脚本设备）
3. `water_treatment` -> 水处理设备

说明：最终以你提供的接口字段为准，前端增加映射层适配。

## 4.3 产品主展示区
1. 标题示例：`水处理系列产品`。
2. 左侧/中部显示主产品图。
3. 右侧显示简介文案。
4. 该区块数据来自接口，可按当前站点主推分类返回。

建议字段：
```json
{
  "sectionTitle": "水处理系列产品",
  "mainImage": "https://xxx/main-product.png",
  "description": "文本描述",
  "ctaText": "查看更多",
  "ctaLink": "/products/water"
}
```

## 4.4 产品列表区
1. 网格布局固定为 3 列，每页 9 条（3 行 x 3 列）。
2. 每个卡片包含：封面图、名称、可选简介。
3. 必须支持分页器（上一页、下一页、页码）。
4. 切换大分类时，分页重置为第 1 页。
5. 分页切换时仅刷新产品列表区，避免整页闪动。

建议字段：
```json
{
  "list": [
    {
      "id": 201,
      "name": "机械过滤器",
      "imageUrl": "https://xxx/p1.jpg",
      "summary": "",
      "detailUrl": "/product/201"
    }
  ],
  "page": 1,
  "pageSize": 9,
  "total": 24
}
```

## 4.5 应用范围区
1. 区块标题：`应用范围`。
2. 横向展示场景图（建议 5 张）。
3. 每张图支持跳转对应案例详情页。

建议字段：
```json
{
  "title": "应用范围",
  "scenes": [
    {
      "id": 301,
      "name": "工业制造",
      "imageUrl": "https://xxx/scene1.jpg",
      "linkUrl": "/case/301"
    }
  ]
}
```

## 4.6 页脚区
1. 深色背景，4 列信息：
   - 关于我们
   - 联系我们
   - 栏目导航
   - 备案/版权
2. 可先静态，后续接 CMS。

## 5. 前端技术方案

## 5.1 推荐目录结构
```text
category/
  category.html
  assets/
    css/
      category.css
    js/
      category-page.js
      category-api.js
      category-render.js
  config/
    home-category-content-config.json
```

## 5.2 状态管理建议
首页状态（无论 Vue/React）建议最小化：
1. `activeCategoryKey`
2. `bannerList`
3. `highlightData`
4. `productList`
5. `sceneList`
6. `loading/error`

## 5.3 渲染时序
1. 页面初始化：
   - 按默认分类并行拉取 Banner、产品主展示、产品列表。
   - 应用范围单独请求一次（不随分类变化）。
2. 分类切换：
   - 重新请求该分类 Banner、产品主展示、产品列表（page=1,pageSize=9）。
3. 产品分页切换：
   - 仅异步请求产品列表（携带当前分类与目标页码）。
   - 不做整页刷新，仅更新文章列表区与分页控件状态。
4. 接口失败：
   - 当前区块降级显示占位内容。

## 6. 接口清单（当前已确认）

### 6.1 三个大分类文章列表接口（WordPress，已确认）
1. 加热器（子分类 `42,43,44,45,46`）  
   `https://zr.jsss999.com/wp-json/wp/v2/posts?categories=42,43,44,45,46&per_page=9&page=1&orderby=date&order=desc`
2. 搅拌设备（子分类 `47,48`）  
   `https://zr.jsss999.com/wp-json/wp/v2/posts?categories=47,48&per_page=9&page=1&orderby=date&order=desc`
3. 水处理设备（子分类 `49,50,51`）  
   `https://zr.jsss999.com/wp-json/wp/v2/posts?categories=49,50,51&per_page=9&page=1&orderby=date&order=desc`

#### 6.1.1 单个子分类查询规则（点击子分类按钮时）
1. 点击子分类时，`categories` 只传当前子分类的固定 `wpCategoryId`。
2. `wpCategoryId` 来源于配置文件 `home-category-content-config.json` 的 `subCategories[].wpCategoryId`。
3. 禁止用中文名称拼接查询参数（例如“导热油加热器”），只用数字 ID。
4. 示例：
   - 导热油加热器（`42`）：  
     `https://zr.jsss999.com/wp-json/wp/v2/posts?categories=42&per_page=9&page=1&orderby=date&order=desc`
   - 搅拌罐（`47`）：  
     `https://zr.jsss999.com/wp-json/wp/v2/posts?categories=47&per_page=9&page=1&orderby=date&order=desc`
   - 分集水器（`51`）：  
     `https://zr.jsss999.com/wp-json/wp/v2/posts?categories=51&per_page=9&page=1&orderby=date&order=desc`

分页规则：
1. 每页固定 `per_page=9`。
2. 翻页时只改 `page`。
3. 总数与总页数从响应头读取：`X-WP-Total`、`X-WP-TotalPages`。
4. 分页交互采用无刷新异步更新（AJAX/fetch），页面其他区块保持不变。
5. 地址栏参数可同步 `page`（History API），但不触发整页跳转。

### 6.2 其他模块接口（待补充）
1. `Banner`（上部大图/轮播数据）
2. `产品主展示`（中间主图+简介）
3. `应用范围`（底部固定区，可先用静态图片配置）

## 7. 样式还原要求
1. 页面背景以浅灰/白为主，模块间间距明显。
2. 导航区使用深色底，白色文字。
3. 主色建议沿用工业蓝（用于按钮、选中态、指示器）。
4. 卡片边框、阴影、留白保持克制，避免过度装饰。
5. 所有图片容器固定比例，使用 `object-fit: cover` 防止拉伸。

## 8. 性能与工程要求
1. Banner 与产品图开启懒加载。
2. 首屏资源控制：大图压缩到合理体积（单图建议 < 300KB，视质量调整）。
3. 接口请求超时建议 8 秒，支持取消重复请求。
4. 组件拆分，避免单文件过大。

## 9. 验收标准（必须满足）
1. 视觉结构与参考图一致（允许细节微调）。
2. Banner 左侧 3 分类可切换，且每个分类展示不同图片集。
3. 切换大分类后，仅 Banner 与中间产品区数据切换，底部应用范围和页脚不变。
4. 产品列表每页 9 条，3 列布局，分页器可用。
5. 接口异常时页面不白屏，有降级展示。
6. PC 主流浏览器可用（Chrome、Edge 最新版）。

## 10. 联调清单（你需要提供）
1. 三个大分类的 `categoryKey` 与显示名称映射。
2. Banner 分类接口与字段定义。
3. 产品主展示接口（是否按分类返回）。
4. 产品列表接口（已确认走 WP posts；前端需读取响应头 `X-WP-Total/X-WP-TotalPages`）。
5. 应用范围接口（固定数据，不按分类返回）。
6. 图片资源域名是否允许跨域与防盗链策略。

## 11. 给 Claude 的执行步骤（可直接照做）
1. 按本文件先搭建首页骨架与样式。
2. 完成 Banner 左侧分类与右侧轮播联动。
3. 接入分类驱动数据流：分类切换仅刷新 Banner、主展示、产品列表。
4. 增加 loading、error、empty 三种状态 UI。
5. 完成产品列表分页（每页 9 条，每行 3 个）。
6. 自测分类切换、分页切换、接口失败、慢网速场景。
7. 提交前输出一份对照清单，逐条对应第 9 节验收标准。

## 12. 备注
1. 当前“搅拌设备/脚本设备”命名可能存在口径差异，最终以你提供的接口 `categoryName` 为准。
2. 如果你后续给的是单一聚合接口，也可在前端拆分映射为多个模块数据源。

## 13. 已确认图片与分类配置（当前版本）

说明：
1. 下述配置用于首页上半部分与中间产品区的分类切换。
2. 底部应用范围和页脚保持固定，不跟分类切换。
3. 图片 URL 直接使用你提供的线上地址，后续可切换为接口返回。

### 13.1 顶部背景 Banner 图
1. `topBannerBg`：`https://static.jsss999.com/upload/zrsite/category/bg/header-2.jpg`

### 13.2 三个大分类与子分类图片

1. 加热器系列产品（`categoryKey: heater`）
   - 默认主图：
     `https://static.jsss999.com/upload/zrsite/category/jiareqi/%E5%8A%A0%E7%83%AD%E5%99%A8%E4%B8%BB%E5%9B%BE.png`
   - 子分类按钮（5 个）：
     - 导热油加热器（`wpCategoryId: 42`）：
       `https://static.jsss999.com/upload/zrsite/category/jiareqi/%E5%AF%BC%E7%83%AD%E6%B2%B9%E5%8A%A0%E7%83%AD%E5%99%A8.jpg`
     - 管道加热器（`wpCategoryId: 43`）：
       `https://static.jsss999.com/upload/zrsite/category/jiareqi/%E7%AE%A1%E9%81%93%E5%8A%A0%E7%83%AD%E5%99%A8.png`
     - 风道加热器（`wpCategoryId: 44`）：
       `https://static.jsss999.com/upload/zrsite/category/jiareqi/%E9%A3%8E%E9%81%93%E5%8A%A0%E7%83%AD%E5%99%A8.png`
     - 电加热器（`wpCategoryId: 45`）：
       `https://static.jsss999.com/upload/zrsite/category/jiareqi/%E7%94%B5%E5%8A%A0%E7%83%AD%E5%99%A8.png`
     - 电加热元件（`wpCategoryId: 46`）：
       `https://static.jsss999.com/upload/zrsite/category/jiareqi/%E7%94%B5%E5%8A%A0%E7%83%AD%E5%85%83%E4%BB%B6.png`

2. 搅拌设备（`categoryKey: mixer`）
   - 默认主图：
     `https://static.jsss999.com/upload/zrsite/category/jiaoban/%E4%B8%BB%E5%88%86%E7%B1%BB%E5%9B%BE.jpg`
   - 子分类按钮（2 个）：
     - 搅拌罐（`wpCategoryId: 47`）：
       `https://static.jsss999.com/upload/zrsite/category/jiaoban/%E6%90%85%E6%8B%8C%E7%BD%90.jpg`
     - 搅拌器（`wpCategoryId: 48`）：
       `https://static.jsss999.com/upload/zrsite/category/jiaoban/%E6%90%85%E6%8B%8C%E5%99%A8.jpg`

3. 水处理设备（`categoryKey: water_treatment`）
   - 默认主图：
     `https://static.jsss999.com/upload/zrsite/category/water/%E4%B8%BB%E5%88%86%E7%B1%BB.png`
   - 子分类按钮（3 个）：
     - 过滤器（`wpCategoryId: 49`）：
       `https://static.jsss999.com/upload/zrsite/category/water/%E8%BF%87%E6%BB%A4%E5%99%A8.png`
     - 除污器（`wpCategoryId: 50`）：
       `https://static.jsss999.com/upload/zrsite/category/water/%E9%99%A4%E6%B1%A1%E5%99%A8.png`
     - 分集水器（`wpCategoryId: 51`）：
       `https://static.jsss999.com/upload/zrsite/category/water/%E5%88%86%E9%9B%86%E6%B0%B4%E5%99%A8.png`

### 13.2.1 子分类与 WP 分类ID 快速对照（用于跳转/筛选）
1. 加热器：`42 导热油加热器`、`43 管道加热器`、`44 风道加热器`、`45 电加热器`、`46 电加热元件`
2. 搅拌设备：`47 搅拌罐`、`48 搅拌器`
3. 水处理设备：`49 过滤器`、`50 除污器`、`51 分集水器`

### 13.3 前端落地配置（统一外部调用）
1. 不再在前端源码内维护 `HOME_CATEGORY_CONFIG` 常量大对象。
2. 统一从外部 JSON 读取配置：`document/home-category-content-config.json`（上线后建议放 OSS 并以 URL 引用）。
3. 前端仅保留读取与映射逻辑，避免 HTML/JS 内联重复维护配置。
4. 该 JSON 已包含：
   - `topBannerBg`
   - `applicationScenes`
   - `typeCategoryMap`（`type=1/2/3`）
   - `categories[].subCategories[].wpCategoryId/imageUrl/defaultCopy`

最小加载示例：

```ts
const configUrl = "/document/home-category-content-config.json";
const config = await fetch(configUrl).then((r) => r.json());

const type = new URLSearchParams(location.search).get("type") || "1";
const activeTypeConfig = config.typeCategoryMap[type] || config.typeCategoryMap["1"];
```

### 13.4 使用规则
1. 大分类切换时，产品主图先展示该分类 `defaultImage`。
2. 点击子分类按钮后，主图切换为该子分类 `imageUrl`。
3. 子分类按钮不存在时，始终显示大分类默认图。
4. 若后续接口返回同结构数据，前端优先使用接口，静态配置作为兜底。
5. 点击子分类按钮请求文章列表时，必须使用该项 `wpCategoryId` 作为 `categories` 参数值，禁止用名称字符串拼接，避免跳转错误。

### 13.5 `type/sub/page` URL 驱动规则（新增）
1. 分类页通过 URL 参数 `type` 决定默认激活的大分类。
2. 约定：
   - `type=1` -> 加热器（默认查 `42,43,44,45,46`）
   - `type=2` -> 搅拌设备（默认查 `47,48`）
   - `type=3` -> 水处理设备（默认查 `49,50,51`）
3. `sub` 为可选子分类参数，存在时优先按 `sub` 查询（例如 `sub=42`）。
4. `page` 为分页参数，翻页时仅异步刷新文章列表，不刷新整页。
5. 若 `type` 缺失或非法，默认回退到 `type=1`。

URL 示例：
1. `category.html?type=1`
2. `category.html?type=2`
3. `category.html?type=3`
4. `category.html?type=1&sub=42`
5. `category.html?type=1&sub=42&page=2`

页面初始化建议逻辑：
1. 读取 URL 参数 `type/sub/page`。
2. 根据 `type` 映射到 `categoryKey` 与默认 `wpChildCategoryIds`。
3. 若有 `sub`，则请求 `categories=sub`；否则请求 `categories=wpChildCategoryIds`。
4. 根据 `page` 请求对应页码（默认 `page=1`）。
5. 点击分页时异步更新列表，可使用 History API 同步地址栏 `page` 参数。

### 13.6 底部应用范围固定图片（不参与分类切换）
1. `https://static.jsss999.com/upload/zrsite/category/yingyong/1.jpg`
2. `https://static.jsss999.com/upload/zrsite/category/yingyong/2.jpg`
3. `https://static.jsss999.com/upload/zrsite/category/yingyong/3.jpg`
4. `https://static.jsss999.com/upload/zrsite/category/yingyong/4.jpg`
5. `https://static.jsss999.com/upload/zrsite/category/yingyong/5.jpg`

前端常量示例：

```ts
export const HOME_SCENE_IMAGES = [
  "https://static.jsss999.com/upload/zrsite/category/yingyong/1.jpg",
  "https://static.jsss999.com/upload/zrsite/category/yingyong/2.jpg",
  "https://static.jsss999.com/upload/zrsite/category/yingyong/3.jpg",
  "https://static.jsss999.com/upload/zrsite/category/yingyong/4.jpg",
  "https://static.jsss999.com/upload/zrsite/category/yingyong/5.jpg",
];
```
