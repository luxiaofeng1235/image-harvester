# WP 自定义 HTML 嵌入标准改造（批量页面版）

## 1. 适用范围
用于将本地独立 HTML（如 `人才招聘.html`、首页类画布页等）嵌入到 WordPress 页面（自定义 HTML 块）时的统一改造。

适用于以下特征页面：
1. 页面主体在 `#xxx-custom` 容器中。
2. 使用 `#scroll_container / #canvas` 的绝对定位画布结构。
3. 依赖 jQuery 与模板脚本（`wopop_all.js`、`rightmenu.js` 等）。

---

## 2. 已验证的核心问题与根因

### 2.1 本地正常，WP 白板/错位
根因：
1. WP 本身已加载 jQuery，页面又重复加载一次，导致脚本冲突。
2. 页面内存在二次注入脚本逻辑（`$('body').append(data)`），触发重复声明（如 `lazyloadRunObserver`）。
3. WP 主题的 `is-layout-constrained` 默认限宽导致内容被压缩。

### 2.2 字体看不见（白底白字）
根因：
1. 主题或页面内联样式带白色字体。
2. 自定义页面背景为白色，文字也被继承为浅色。

### 2.3 页脚看不到/底部空白过大
根因：
1. 画布高度与 WP 容器滚动规则冲突。
2. `#canvas` 高度策略与页面绝对定位图层不匹配。

### 2.4 左侧“回到顶部”按钮无效
根因：
1. 侧边栏脚本默认滚动 `#scroll_container`。
2. WP 场景实际滚动目标可能是 `html/body`，导致点击无反应。

---

## 3. 每个 HTML 必做改造（统一规则）

## 3.1 jQuery 兼容加载（必须）
把原始的直接 jQuery 引入：

```html
<script src="https://static.jsss999.com/upload/zrsite/common/jquery-3.7.1.min.js"></script>
```

改成：

```html
<script>
  if (!window.jQuery) {
    document.write('<script src="https://static.jsss999.com/upload/zrsite/common/jquery-3.7.1.min.js"><\\/script>');
  }
</script>
<script>
  window.$ = window.jQuery;
</script>
```

目的：本地可跑，WP 内不重复加载。

## 3.2 禁用“购物车二次注入脚本”（必须）
删除或注释整段：

```js
$(function () {
  $.post(parseToURL("tb_shopping_cart", "showShoppingBags"), function (data) {
    $('#wp-shopping-bags').remove();
    $('body').append(data);
  });
});
```

目的：避免 append 带 `<script>` 的片段导致重复声明错误。

## 3.3 画布容器写法（建议）
`#canvas` 内联样式建议：

```html
<div id="canvas" style="margin:0 auto; width:1500px; height:auto;">
```

说明：
1. 如果出现“内容贴页脚”或“底部空白过大”，优先通过页面级 CSS 的 `#canvas` 高度微调。
2. 不同页面高度不同，建议按页面实际微调，不要全站一个固定值。

## 3.4 回到顶部兜底（建议）
在页面底部追加兜底脚本：

```html
<script>
(function () {
  function forceGoTop() {
    var sc = document.getElementById('scroll_container');
    if (sc) {
      try { sc.scrollTo({ top: 0, behavior: 'smooth' }); } catch (e) { sc.scrollTop = 0; }
      sc.scrollTop = 0;
    }
    try { window.scrollTo({ top: 0, behavior: 'smooth' }); } catch (e) { window.scrollTo(0, 0); }
    document.documentElement.scrollTop = 0;
    document.body.scrollTop = 0;
  }

  document.addEventListener('click', function (e) {
    var hit = e.target.closest('.wpsidebar02 li.sgotop, .wpsidebar03 .sgotop, li.sgotopdd, .wp_celan_content p.ptop');
    if (!hit) return;
    e.preventDefault();
    e.stopPropagation();
    forceGoTop();
  }, true);
})();
</script>
```

---

## 4. 页面级 CSS 模板（每页一份）
> 注意：`page-id-794` 需替换成目标页面的真实 page id。

```css
/* 宽度与容器 */
body.page-id-794 .medu-main .entry-content,
body.page-id-794 .medu-main .wp-block-post-content{
  max-width:100% !important;
  width:100% !important;
  padding-left:0 !important;
  padding-right:0 !important;
}

body.page-id-794 .medu-main .is-layout-constrained > :where(:not(.alignleft):not(.alignright):not(.alignfull)){
  max-width:none !important;
  margin-left:0 !important;
  margin-right:0 !important;
}

body.page-id-794 .medu-main [id$="-custom"]{
  width:100% !important;
  max-width:none !important;
  margin:0 !important;
}

/* 滚动与页脚 */
html body.page-id-794{
  overflow-y:auto !important;
}

body.page-id-794 #scroll_container,
body.page-id-794 #overflow_canvas_container{
  height:auto !important;
  overflow:visible !important;
}

/* 按页面微调：必要时启用 */
/* body.page-id-794 #canvas{
  min-height:2837px !important;
  height:2837px !important;
  overflow:visible !important;
} */

body.page-id-794 footer.wp-block-template-part{
  position:relative;
  z-index:999;
  display:block !important;
}

/* 白底白字修复 */
body.page-id-794 .medu-main [id$="-custom"],
body.page-id-794 .medu-main [id$="-custom"] p,
body.page-id-794 .medu-main [id$="-custom"] span,
body.page-id-794 .medu-main [id$="-custom"] li,
body.page-id-794 .medu-main [id$="-custom"] h1,
body.page-id-794 .medu-main [id$="-custom"] h2,
body.page-id-794 .medu-main [id$="-custom"] h3,
body.page-id-794 .medu-main [id$="-custom"] h4,
body.page-id-794 .medu-main [id$="-custom"] h5,
body.page-id-794 .medu-main [id$="-custom"] h6,
body.page-id-794 .medu-main [id$="-custom"] strong,
body.page-id-794 .medu-main [id$="-custom"] em{
  color:#111 !important;
}

body.page-id-794 .medu-main [id$="-custom"] .has-white-color,
body.page-id-794 .medu-main [id$="-custom"] [style*="color:#fff"],
body.page-id-794 .medu-main [id$="-custom"] [style*="color: #fff"],
body.page-id-794 .medu-main [id$="-custom"] [style*="color:rgb(255, 255, 255)"],
body.page-id-794 .medu-main [id$="-custom"] [style*="color: rgb(255, 255, 255)"]{
  color:#111 !important;
}

body.page-id-794 .medu-main [id$="-custom"] a{
  color:#1f6fbf !important;
}
body.page-id-794 .medu-main [id$="-custom"] a:hover{
  color:#0f4f90 !important;
}
```

---

## 5. 批量嵌入流程（7-8 页复用）
1. 为每个页面创建或确认 WP 页面，记录 `page-id`。
2. 复制本地 HTML，应用第 3 节改造（jQuery 条件加载 + 去掉购物车注入）。
3. 粘贴到 WP 自定义 HTML 区块。
4. 在 CSS&JS 插件新增一条“页面限定 CSS”，把 `page-id-794` 替换为当前页 id。
5. 清缓存（CSS/JS 插件、WP 缓存、CDN 缓存）。
6. 强刷（`Ctrl+F5`）验收。

---

## 6. 验收清单
1. 页面主体正常显示，无白板。
2. 控制台无 `jQuery is not defined`。
3. 控制台无 `lazyloadRunObserver has already been declared`。
4. 文字不是白底白字。
5. 页脚可见、底部空白可接受。
6. 左侧“回到顶部”可点击并生效。

---

## 7. 已知可忽略告警
`Failed to load resource: ... s=64&d=mm&r=g (TIMED_OUT)` 多为头像资源超时，通常不影响页面主功能。

---

## 8. 注意事项
1. CSS 块里不要混入说明文字（如“2. 只保留这版...”），否则会污染样式解析。
2. 每页尽量使用页面级选择器（`body.page-id-xxx`），避免误伤全站。
3. 如果某页仍有底部空白，优先微调该页 `#canvas` 的 `min-height/height`，不要全站统一改。
