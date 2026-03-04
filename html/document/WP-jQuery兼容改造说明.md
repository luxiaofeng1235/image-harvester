# WP 页面 jQuery 兼容改造说明

## 一、改造背景

旧站（www.zgzonre.com）使用建站平台自带的合并 JS 加载方式，包含旧版 jQuery 及多个已废弃的库。迁移到 WP 后，需要将完整 HTML 页面转换为 `<div>` 片段格式嵌入，同时升级 jQuery 并清理废弃资源。

## 二、jQuery 版本对照

| 项目 | 旧站（线上） | WP 改造后 |
|------|-------------|-----------|
| jQuery 版本 | libsjq.js（jQuery 1.x/2.x） | jquery-3.7.1.min.js |
| 兼容垫片 | 无 | compat-shim-v1.3.js |
| 加载方式 | 合并 JS（`script/??libsjq.js,jquery.custom.js,...`） | 独立文件逐个加载 |

## 三、JS 文件对照

### 保留并替换为独立加载的 JS

| 旧站合并 JS 中的文件 | 替换为 OSS 独立文件 |
|---------------------|-------------------|
| libsjq.js | `https://static.jsss999.com/upload/zrsite/common/jquery-3.7.1.min.js` |
| （无） | `https://static.jsss999.com/upload/zrsite/common/compat-shim-v1.3.js`（新增垫片） |
| jquery.custom.js | `https://static.jsss999.com/upload/zrsite/index/jquery.custom.js` |
| jquery.lazyload.js | `https://static.jsss999.com/upload/zrsite/index/jquery.lazyload.js` |
| jquery.rotateutility.js | `https://static.jsss999.com/upload/zrsite/index/jquery.rotateutility.js` |
| lab.js | `https://static.jsss999.com/upload/zrsite/index/lab.js` |
| wopop_all.js | `https://static.jsss999.com/upload/zrsite/index/wopop_all.js` |
| fullcollumn.js | `https://static.jsss999.com/upload/zrsite/index/fullcollumn.js` |
| ierotate.js | `https://static.jsss999.com/upload/zrsite/index/ierotate.js` |
| effects/velocity.js | `https://static.jsss999.com/upload/zrsite/index/velocity.js` |
| effects/velocity.ui.js | `https://static.jsss999.com/upload/zrsite/index/velocity.ui.js` |
| effects/effects.js | `https://static.jsss999.com/upload/zrsite/index/effects.js` |
| fullpagescroll.js | `https://static.jsss999.com/upload/zrsite/index/fullpagescroll.js` |
| common.js | `https://static.jsss999.com/upload/zrsite/index/common.js` |
| heightAdapt.js | `https://static.jsss999.com/upload/zrsite/index/heightAdapt.js` |

### 已废弃删除的 JS

| 文件 | 删除原因 |
|------|---------|
| jquery.cookie.js | jQuery 3.x 不再需要，现代浏览器原生支持 |
| jquery.simplemodal.js | 依赖已移除的 jQuery API，页面未实际使用 |
| objectFitPolyfill.min.js | 现代浏览器原生支持 object-fit |

### 保留不变的插件组合 JS

```
https://static.ysjianzhan.cn/website/plugin/??unslider/js/init.js,new_navigation/js/overall.js,new_navigation/styles/hs12/init.js,media/js/init.js,buttons/js/init.js,sitesearch/js/init.js
```

> 此文件来自建站平台 CDN，所有页面共用，保持原样加载。

## 四、CSS 文件对照

| 旧站 CSS | 替换为 OSS 文件 |
|----------|----------------|
| `static.ysjianzhan.cn/.../default.css` | `https://static.jsss999.com/upload/zrsite/index/default.css` |
| `www.zgzonre.com/.../font.css` | `https://static.jsss999.com/upload/zrsite/index/font.css` |
| `www.zgzonre.com/.../iconfont.css` | `https://static.jsss999.com/upload/zrsite/index/iconfont.css` |
| `static.ysjianzhan.cn/.../unslider.css` | `https://static.jsss999.com/upload/zrsite/index/unslider.css` |
| `static.ysjianzhan.cn/.../sidebar.css` | 保留原地址（sidebar 基础样式） |
| `static.ysjianzhan.cn/.../title.css` | `https://static.jsss999.com/upload/zrsite/index/title.css` |
| `static.ysjianzhan.cn/.../media.css` | `https://static.jsss999.com/upload/zrsite/index/media.css` |
| `static.ysjianzhan.cn/.../sidebar02.css` | `https://static.jsss999.com/upload/zrsite/index/sidebar02.css` |
| `static.ysjianzhan.cn/.../sitesearch.css` | **已删除**（页面未使用搜索组件） |
| `www.zgzonre.com/xxx.cssx`（页面专属样式） | `https://static.jsss999.com/upload/zrsite/common/common_layers-v1.css` |

### common_layers-v1.css 说明

此文件从各页面的 `.cssx` 中提取，包含页面组件的专属样式，是**公用文件**，多个页面共享引用：

- 轮播 unslider 导航点样式
- 侧边栏 sidebar02 自定义样式
- page114 三个"更多产品"按钮样式（`button_btnoval`）
- page114 三条分割线样式
- 首页"更多案例"按钮样式（`button_circle`）

> **版本管理**：OSS 有缓存，更新内容时需改文件名（如 v1 → v2），同步修改所有页面的引用。

## 五、废弃 jQuery API 替换

| 废弃 API | 替换方式 | 说明 |
|----------|---------|------|
| `$.parseJSON(...)` | `JSON.parse(...)` | 源码直接替换 |
| `.live('click', fn)` | `$(document).on('click', selector, fn)` | 源码直接替换 |
| `$.browser.msie` | 由 compat-shim 垫片兜底 | 插件内部调用，无法改源码 |
| `$.parseInteger(...)` | 由 compat-shim 垫片兜底 | fullcolumn 脚本使用 |

### compat-shim-v1.3.js 垫片覆盖的 API

垫片补回了 jQuery 3.x 中已移除但旧代码仍依赖的 API：

- `$.browser` / `$.browser.msie` / `$.browser.version`
- `$.parseInteger`
- 其他建站平台插件内部依赖的兼容方法

> 能在源码层面直接改的（`.live()`、`$.parseJSON`）已直接改掉，不依赖垫片。

## 六、域名替换

| 旧域名 | 新域名 |
|--------|--------|
| `https://www.zgzonre.com` | `https://www.zgzonre.com` |

涉及位置：
- `p_rooturl` 配置
- `punyurl` 配置
- 所有页面内链接（`/pageXXX`）

## 七、页面转换格式

每个页面从完整 HTML 转换为 `<div>` 片段：

- 去掉 `<!DOCTYPE>`、`<html>`、`<head>`、`<body>` 外壳标签
- 整体包裹在 `<div id="xxx-custom">` 中
- `<head>` 中有用的 CSS 引用移入片段顶部
- 去掉 meta、title、favicon 等（由 WP 主题提供）
- 去掉 `.cssx` 引用（样式已提取到 common_layers-v1.css）

## 八、已改造页面清单

| 页面 | 文件 | 包裹 ID | 状态 |
|------|------|---------|------|
| 首页 | 首页.html | `home-custom` | 已完成 |
| 产品展示 | page114_source.html | `page114-custom` | 已完成 |

## 九、验证检查项

上传到 WP 后逐项检查：

- [ ] F12 控制台无红色报错
- [ ] 图片悬浮效果（wopop_imgeffects: effect.slidetop）正常
- [ ] "更多产品"/"更多案例"按钮有圆角背景样式
- [ ] 轮播图正常切换
- [ ] 侧边栏悬浮菜单正常显示
- [ ] 页面内链接跳转到 `www.zgzonre.com` 域名

## 十、后续维护注意

1. **新增页面改造时**：如果页面有 `.cssx` 文件，需要提取其中的组件样式追加到 `common_layers-vX.css`，更新版本号并重新上传 OSS
2. **OSS 缓存**：修改 CSS 内容后必须改文件名（递增版本号），否则缓存不会更新
3. **垫片版本**：如遇到新的兼容问题，检查 `compat-shim-v1.3.js` 是否需要更新
