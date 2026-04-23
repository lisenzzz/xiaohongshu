# 小红书博主内容爬虫使用说明

## 快速开始

```bash
# 1. 激活虚拟环境
source .venv/bin/activate

# 2. 编辑配置，填入 Cookie
open scripts/config.py

# 3. 运行爬虫
python scripts/xhs_scraper.py
```

## 第一步：获取 Cookie

小红书 API 需要登录态的 Cookie 才能访问。步骤如下：

1. 用 Chrome 浏览器打开 https://www.xiaohongshu.com 并**登录**
2. 按 `F12` 打开开发者工具
3. 切换到 **Network** 标签
4. 刷新页面 (`Cmd+R` 或 `Ctrl+R`)
5. 点击列表中任意一个发往 `xiaohongshu.com` 的请求
6. 在 **Request Headers** 区域找到 `cookie:` 那一行
7. 复制 `cookie:` 后面的**整行内容**（很长，以 `a1=...` 开头居多）
8. 打开 `scripts/config.py`，把内容粘贴到 `COOKIES = ""` 的引号中

> Cookie 有效期通常为几小时到几天，过期后需要重新获取。

## 第二步：运行

```bash
# 爬取所有账号（自己 + 竞品）
python scripts/xhs_scraper.py

# 只爬取自己的账号
python scripts/xhs_scraper.py --account own

# 只爬取竞品账号
python scripts/xhs_scraper.py --account competitor

# 调试模式（打印第一条笔记的原始 API 响应，用于排查字段问题）
python scripts/xhs_scraper.py --debug
```

## 输出

报告自动保存到 `posts/ideas/engagement_report_YYYYMMDD.md`，包含：

- 每个账号的数据概览（总笔记、平均互动、最高互动）
- 高互动帖子 Top 20（标题、点赞、收藏、评论、日期、链接）
- 高互动帖子标题关键词
- 内容形式表现（图文 vs 视频）
- 跨账号对比
- 选题建议

## 添加更多竞品账号

编辑 `scripts/config.py`，在 `ACCOUNTS` 字典中添加：

```python
ACCOUNTS = {
    "own": {
        "name": "上海思辨写作云老师",
        "user_id": "5b6f9a34e24fb70001888f8b",
    },
    "competitor": {
        "name": "竞品账号",
        "user_id": "6039c2b9000000000100652b",
    },
    # 添加更多竞品：
    "competitor2": {
        "name": "另一个竞品",
        "user_id": "这里填用户ID",
    },
}
```

用户 ID 从主页链接中获取：`https://www.xiaohongshu.com/user/profile/用户ID`

## 常见问题

### Cookie 过期 / API 返回登录错误

重新从浏览器获取 Cookie，粘贴到 `config.py`。

### x-s 签名错误

小红书 API 有请求签名机制。如果遇到签名错误：

1. 在浏览器中打开小红书任意页面
2. F12 → Network → 找一个发往 `edith.xiaohongshu.com` 的请求
3. 复制 Request Headers 中的 `x-s` 和 `x-t` 值
4. 粘贴到 `config.py` 的 `HEADERS` 中对应位置

### 获取到的笔记数为 0

- 检查 `user_id` 是否正确
- 确认该账号有公开的笔记
- 尝试 `--debug` 模式查看原始响应

### 限流 / 429 错误

脚本会自动等待 30 秒后重试。如果频繁出现，增大 `config.py` 中的 `REQUEST_DELAY`。

## 技术细节

- API 端点：`GET https://edith.xiaohongshu.com/api/sns/web/v1/user_posted`
- 分页方式：cursor-based，每页最多 30 条
- 请求间隔：默认 2 秒
- 互动指标：点赞 + 收藏 = 总互动量
