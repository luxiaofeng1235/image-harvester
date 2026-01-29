# 开发规范

## 采集器接口
- 每个源实现 `fetch_urls(keyword, limit)`
- 返回标准化 URL 列表（字符串）
- 内部处理分页、重试、限速

## Pipeline 规则
- URL 去重 + 内容哈希去重
- 下载前优先探测 Content-Type/尺寸
- 按规则过滤分辨率
- 输出目录：`out/YYYYMMDD/width-height/`

## 合规
- 源可配置、可禁用
- 支持 `blocked_domains`
- 不绕过验证码、登录、付费墙

## 测试
- 不依赖真实网络
- 覆盖：URL 解析、去重、分辨率过滤
