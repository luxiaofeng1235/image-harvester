# 页面改造提速 SOP（下午 3 页通用）

> 目标：30 分钟内完成 1 页（扒取 + 去导航页脚 + 幻灯片/视频 + 平铺 OSS + 验收）

## 1. 固定规则（必须遵守）

1. 不引用 `www.zgzonre.com`（页面运行依赖必须剥离）
2. OSS 使用平铺路径，不分子目录（例如：`.../jiareqi/video-1.html`）
3. 每页在 `out/<pageKey>/` 单独目录工作
4. 导航栏和页脚删除，主体和幻灯片保留
5. 视频使用“壳页 + 远程 mp4”模式（与 page172/page173 一致）
6. 图片下载使用 `User-Agent + Referer`（防盗链）

---

## 2. 单页目录标准

以 `page173` 为例：

```text
out/page173/
  page173-source.html
  page173-embed-min.html
  css/
    page173.cssx
  image/
    myo1.jpg
    0anf.png
    wysm.png
    left_arrow.png
    right_arrow.png
  video/
    video-1.html ... video-10.html
    poster-1.jpg ... poster-10.jpg
  manifest.txt
```

---

## 3. 快速执行流程（每页）

1. 下载源码到 `out/<pageKey>/page-source.html`
2. 定位并删除：
   - 顶部导航层（一般 `new_navigation` 或顶部 `full_column`）
   - 页脚层（一般 `site_footer`）
3. 提取页面专属 cssx：
   - 如 `<link href="https://xxx/<hash>.cssx">` 下载到 `css/<pageKey>.cssx`
4. 处理幻灯片：
   - 图片按防盗链方式下载（UA+Referer）
   - 箭头改成本地文件或 OSS 文件
5. 处理视频：
   - 把 `zgzonre.com/index.php?...video_iframe` 改为 `video-N.html`
   - `video-N.html` 内部直连远程 mp4 + 本地/OSS poster
6. 将主页面资源改为平铺 OSS 绝对路径（最终版）
7. 产出 `manifest.txt`（给上传和核对用）

---

## 4. 防盗链下载模板（图片）

```bash
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
REF='https://www.zgzonre.com/page173'
curl -L -A "$UA" -e "$REF" \
  -H 'Accept: image/avif,image/webp,image/apng,image/*,*/*;q=0.8' \
  'https://pro23233665-pic5.ysjianzhan.cn/upload/0anf.png' \
  -o out/page173/image/0anf.png
```

---

## 5. 视频壳页模板（video-N.html）

```html
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    html,body{margin:0;padding:0;width:100%;height:100%;background:#000;overflow:hidden;}
    video{display:block;width:100%;height:100%;object-fit:cover;background:#000;}
  </style>
</head>
<body>
  <video controls preload="metadata" loop poster="./poster-1.jpg">
    <source src="https://static-nine-world.oss-cn-shanghai.aliyuncs.com/zgzonre_video/xxx.mp4" type="video/mp4" />
  </video>
</body>
</html>
```

---

## 6. 平铺 OSS 替换规则（最终版）

假设基础路径：

`https://static.jsss999.com/upload/zrsite/index/jiareqi`

则页面中统一替换为：

1. `./css/page173.cssx` -> `.../jiareqi/page173.cssx`
2. `./image/myo1.jpg` -> `.../jiareqi/myo1.jpg`
3. `./video/video-1.html` -> `.../jiareqi/video-1.html`
4. `./video/poster-1.jpg` -> `.../jiareqi/poster-1.jpg`（在 `video-1.html` 内）

注意：不要替换成 `.../jiareqi/css/...` 或 `.../jiareqi/video/...`（你当前 OSS 是平铺）

---

## 7. 交付前验收（必须）

1. 资源状态码检查（抽查）

```bash
curl -I https://static.jsss999.com/upload/zrsite/index/jiareqi/page173.cssx
curl -I https://static.jsss999.com/upload/zrsite/index/jiareqi/video-1.html
curl -I https://static.jsss999.com/upload/zrsite/index/jiareqi/poster-1.jpg
```

要求：全部 `200`

2. 域名依赖检查

```bash
rg -n 'www\\.zgzonre\\.com' out/page173/page173-embed-min.html out/page173/video/video-*.html
```

要求：无输出

3. 视频有效性检查（Playwright 或浏览器）

- 打开 `video-1.html` / `video-10.html`
- 有封面，点播放可播，控制条正常

---

## 8. 常见坑位

1. `pic5` 域名有 `-` 和 `.` 两种写法，错一个就 404
2. 图片下载成 150B/552B HTML 占位，说明被防盗链或路径错
3. `page173-embed-min.html` 不一定上 OSS（嵌入 WP 时可只贴代码）
4. 视频黑屏通常不是 mp4 挂了，而是 `poster` 或 `iframe` 壳页路径错

---

## 9. 下午三页执行建议

1. 先做“结构裁剪 + 幻灯片”
2. 再做“视频壳页”
3. 最后统一“平铺 OSS 替换 + 200 验收”
4. 每页完成后留 `manifest.txt`，避免传漏

