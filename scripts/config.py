# -*- coding: utf-8 -*-

# ============================================
# 小红书爬虫配置文件
# 使用前请按说明填写 Cookie
# ============================================

# --- Cookie 配置 ---
# 如何获取 Cookie：
# 1. 用 Chrome 打开 https://www.xiaohongshu.com 并登录
# 2. 按 F12 打开开发者工具 → Network 标签
# 3. 刷新页面，点击任意一个发往 xiaohongshu.com 的请求
# 4. 在 Request Headers 中找到 "cookie:"，复制其值粘贴到下面
COOKIES = "gid=yjJKWdYJf0EdyjJKWdYJYT7I22FuK0C4UiMk6kyhdCKAE0q8USfduU888qjJq4K884880jDy; customerClientId=836494676395256; abRequestId=0ae85670-ed50-59b8-8be3-fe98a7d0bcc4; a1=19a82affc7br4q80g9km0cc5ytimvtkcd7i9e28qq30000192193; webId=859c1b747197e5631ee1f5970ce48553; x-user-id-zhaoshang.xiaohongshu.com=5b6f9a34e24fb70001888f8b; x-user-id-redlive.xiaohongshu.com=5b6f9a34e24fb70001888f8b; x-user-id-creator.xiaohongshu.com=5b6f9a34e24fb70001888f8b; web_session=04006978e9969266dfddbc98453b4ba864ab19; id_token=VjEAAIlaRgAzduGKcMyKvfSyK/9ao47bp9IfoZKObMZXxtBDbzGKY3IOJRi9yaGOrhbO/zKhbP2hjl0eTHE2cH6c+hXrjwf+zgRDZrGxOXybkY1sZ0Hg6fMX+ZNpmgKb+vJj7bn1; x-user-id-ark.xiaohongshu.com=5b6f9a34e24fb70001888f8b; ets=1775572340072; access-token-creator.xiaohongshu.com=customer.creator.AT-68c517626026115694608385iwhypqleict5nmym; galaxy_creator_session_id=amM0IrJ3xb66OqZZ42sFQAPkZ1ZBhzliwrMO; galaxy.creator.beaker.session.id=1775572569129065690756; webBuild=6.7.0; unread={%22ub%22:%2269e31cbc000000002301e643%22%2C%22ue%22:%2269e3690f0000000021013890%22%2C%22uc%22:26}; websectiga=8886be45f388a1ee7bf611a69f3e174cae48f1ea02c0f8ec3256031b8be9c7ee; xsecappid=xhs-pc-web; sec_poison_id=b6b32763-079d-470f-b878-472b505ed660; loadts=1776527295068"

# --- 目标账号 ---
ACCOUNTS = {
    "own": {
        "name": "上海思辨写作云老师",
        "user_id": "5b6f9a34e24fb70001888f8b",
    },
    "competitor": {
        "name": "竞品账号",
        "user_id": "6039c2b9000000000100652b",
    },
}

# --- 爬取设置 ---
NOTES_PER_PAGE = 30       # 每次请求获取的笔记数
MAX_PAGES = 20            # 最大翻页数（20 * 30 = 600条上限）
REQUEST_DELAY = 2.0       # 请求间隔秒数（避免触发反爬）
TOP_N = 20                # 报告中展示的高互动帖子数量

# --- 输出设置 ---
REPORT_DIR = "posts/ideas"

# --- 请求 Headers ---
# x-s 和 x-t 如果 API 返回签名错误，需要从浏览器 Network 面板中复制
HEADERS = {
    "authority": "edith.xiaohongshu.com",
    "accept": "application/json, text/plain, */*",
    "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
    "origin": "https://www.xiaohongshu.com",
    "referer": "https://www.xiaohongshu.com/",
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "x-s": "",
    "x-t": "",
}
