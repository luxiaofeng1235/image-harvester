# WordPress「联系我们」页面植入兼容改造方案

> 目标：**复用现有业务 HTML**，并做到 **WP 线上页面样式/JS 不被污染**，同时尽量降低改造成本与上线风险。

## 背景

- 线上站点：WordPress **6.9.1**
- 业务页面：`联系我们.html`（从仿站导出的一整页代码，包含大量外链 CSS/JS）
- 业务代码现状：页面内包含 `$(...).live(...)`（已在新版本 jQuery 中移除的 API），并且加载了 `libsjq.js`（内置一整套老 jQuery）。

## 主要风险（为什么直接贴到 WP 页面会不稳）

1. **jQuery 冲突**
   - WP 前台通常已加载较新 jQuery（主题/插件依赖）。
   - 业务页又加载 `libsjq.js`（内置老 jQuery），很可能覆盖 `window.$/window.jQuery`。
   - 结果：业务可能正常，但 WP 主题/插件脚本可能异常；或业务脚本执行顺序被优化插件影响导致直接报错。

2. **老 API `.live()` 不兼容**
   - `.live()` 在 jQuery 1.9+ 已移除。
   - 如果业务没有正确加载老 jQuery，就会出现 `live is not a function`。

3. **CSS 污染**
   - 业务外链 CSS 可能包含全局选择器，直接影响 WP 主题样式。

结论：如果要“可控、稳定、可回归”，需要做**隔离**。

---

## 方案 A（强烈推荐）：iframe 承载业务页（最稳、隔离最彻底）

### 适用场景

- 追求上线稳定。
- 允许“联系我们页面”以 iframe 方式展示（视觉可与主题融合，但 DOM/JS/CSS 运行时隔离）。

### 核心思路

1. 将业务页面作为**独立完整 HTML**部署到静态地址（如 `static.jsss999.com`）。
2. WP 页面内容只嵌入一个 iframe。
3. iframe 内通过 `postMessage` 上报高度，父页面动态调整 iframe 高度（避免固定高度带来的留白/截断）。

### 实施步骤

#### Step 1：生成独立业务页（iframe 内页面）

- 新建一个完整 HTML（示例文件名：`contact-embed.html`）。
- `<body>` 中直接复用现有 `联系我们.html` 的内容块（例如 `<div id="contact-custom">...</div>`）。
- **保留原业务外链 CSS/JS 顺序**（含 `libsjq.js`），因为都在 iframe 内运行，不会污染 WP。

在 `</body>` 前追加高度上报脚本：

```html
<script>
(function () {
  function sendHeight() {
    var h = Math.max(
      document.documentElement.scrollHeight,
      document.body ? document.body.scrollHeight : 0
    );
    parent.postMessage({ type: "zonre-contact-height", height: h }, "*");
  }

  window.addEventListener("load", sendHeight);
  window.addEventListener("resize", sendHeight);
  if (window.ResizeObserver) new ResizeObserver(sendHeight).observe(document.documentElement);

  // 兼容：某些资源异步加载后高度变化
  setTimeout(sendHeight, 300);
  setTimeout(sendHeight, 1200);
})();
</script>
```

#### Step 2：WP 页面嵌入 iframe

在 WP 的“自定义 HTML”区块中放入：

```html
<iframe
  id="zonre-contact-iframe"
  src="https://static.jsss999.com/你的路径/contact-embed.html"
  style="width:100%;height:2200px;border:0;display:block;"
  loading="lazy"
></iframe>

<script>
window.addEventListener("message", function (e) {
  if (!e.data || e.data.type !== "zonre-contact-height") return;
  var iframe = document.getElementById("zonre-contact-iframe");
  if (!iframe) return;
  var h = parseInt(e.data.height, 10);
  iframe.style.height = (Number.isFinite(h) && h > 0 ? h : 2200) + "px";
});
</script>
```

> 初始高度 `2200px` 可参考业务页 `#canvas` 的固定高度设置；上线后再微调。

### 优点

- **JS/CSS 天然隔离**：业务 jQuery/全局变量不会影响 WP。
- **无需处理 `.live()`**：业务页可继续使用旧 jQuery 运行。
- 改造成本最低，回归测试点最少。

### 注意事项

- SEO：iframe 内容对 WP 页面 SEO 不如原生渲染（如果你只需要展示联系信息，一般可接受）。
- 同域/跨域：`postMessage` 用 `*` 方便，但更安全可将 `*` 改为指定域名白名单。

---

## 方案 B（备选，不推荐但可做）：同页嵌入 + 使用 WP jQuery + 替换 `.live()` 为委托 `.on()`

### 适用场景

- 必须与 WP 同一 DOM 渲染（不用 iframe）。
- 能接受对业务 HTML/JS 做一定改造并进行更充分回归测试。

### 核心思路

1. **不再加载** `libsjq.js`（避免覆盖 WP 的 jQuery）。
2. 使用 WP 自带 jQuery（3.x 系列）并遵循 noConflict 写法：`jQuery(function($){ ... })`。
3. 将 `.live()` 替换为事件委托 `.on()`。
4. CSS 尽量隔离：建议将业务 CSS 做一份“前缀化版本”（所有选择器加 `#contact-custom`），只对该容器生效。

### `.live()` 替换示例

将：

```js
$(".content_copen").live("click", function () {
  $(this).closest(".full_column").hide();
});
```

改为（推荐限定在容器 `#contact-custom` 内）：

```js
jQuery(function ($) {
  $("#contact-custom").on("click", ".content_copen", function () {
    $(this).closest(".full_column").hide();
  });
});
```

### CSS 隔离说明

- “新增几条 CSS”无法真正隔离全量业务 CSS。
- 真正有效的隔离方式是：
  - 把业务 CSS 重新生成一份：所有选择器统一加 `#contact-custom` 前缀（工程化批处理），然后只加载这份前缀化 CSS。

### 风险提示

- 业务外链 `jquery.*.js` 插件可能依赖老 jQuery 行为，替换为 WP jQuery 后可能需要逐个适配。
- 同页嵌入不可避免与主题/插件脚本共享运行时，回归成本高。

---

## 上线前检查清单（两种方案都建议做）

1. 浏览器控制台无报错（尤其是 `$ is not a function`、`live is not a function`）。
2. Network 面板确认业务外链 CSS/JS 全部 200。
3. 点击/滚动/弹层/侧边栏交互可用。
4. WP 主题菜单/页脚脚本在该页仍正常（方案 B 必测）。

## 常见问题：iframe 内中文乱码（编码不正确）

现象：iframe 内中文显示为乱码（例如出现类似 `å…`、`é…` 的字符）。

原因：

- OSS/HTTP 响应头为 `Content-Type: text/html`，未声明 `charset=utf-8`，浏览器可能按错误编码猜测。
- HTML 文件本身也没有 `<meta charset="utf-8">`。

修复（推荐二选一）：

1. 将静态页改为完整 HTML，并在 `<head>` 内加入：

```html
<meta charset="utf-8" />
```

2. 在 OSS 对象元数据中将 `Content-Type` 设置为：

```txt
text/html; charset=utf-8
```

## 常见问题：iframe 宽度不够（被主题内容区限制）

现象：iframe 只占页面内容区宽度，看起来很窄。

解决：使用 100vw 让 iframe 拉满视口宽度（不依赖主题是否全宽模板）：

```html
<div style="position:relative;left:50%;right:50%;margin-left:-50vw;margin-right:-50vw;width:100vw;max-width:100vw;overflow:hidden;">
  <iframe
    src="https://static.jsss999.com/upload/zrsite/html/contact.v2.html"
    width="100%"
    height="2200"
    style="width:100vw;max-width:100vw;height:2200px;border:0;display:block;overflow:hidden;"
    scrolling="no"
  ></iframe>
</div>
```

## 推荐结论

- **优先使用方案 A（iframe）**：隔离最彻底，最适合“复用整页 HTML 且不影响 WP 其他部分”的目标。
- 只有在必须同页渲染时，才考虑方案 B，并准备更充分的回归测试。

## 已知错误排查：`$.divrotate` 相关报错

现象示例：

```
Uncaught TypeError: Cannot read properties of undefined (reading 'getDegreeModMaxPointOrigin')
  at helperfunc (wopop_all.js:623:30)
```

原因：

- `wopop_all.js` 中会调用 `$.divrotate.getDegreeModMaxPointOrigin(...)`。
- 若页面未加载 `jquery.rotateutility.js`（提供 `$.divrotate`），则会出现上述报错。

修复：

- 确保在加载 `wopop_all.js` 之前加载：

```html
<script src="https://static.jsss999.com/upload/zrsite/index/jquery.rotateutility.js"></script>
```

补充：如果控制台出现 `rotateDom is not defined`（通常由 `wopop_all.js` 调用），再补充加载：

```html
<script src="https://static.jsss999.com/upload/zrsite/index/ierotate.js"></script>
```
