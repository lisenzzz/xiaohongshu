# -*- coding: utf-8 -*-
"""
小红书搜索选题脚本
搜索指定关键词的热门帖子，分析可借鉴的选题方向，生成本地报告。
用法: python scripts/xhs_search_topics.py [--keyword "自定义关键词"] [--sort hot|general|new] [--debug]
"""

import json
import random
import re
import time
import os
import sys
from collections import Counter
from datetime import datetime
from urllib.parse import quote

import requests

# 加载同目录下的 config
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

# Playwright 可选依赖
try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False


# ============================================================
# 工具函数
# ============================================================

def parse_cookies(cookie_string):
    """把 'key1=val1; key2=val2' 格式的字符串转成 dict"""
    cookies = {}
    for item in cookie_string.split(";"):
        item = item.strip()
        if "=" in item:
            key, _, value = item.partition("=")
            cookies[key.strip()] = value.strip()
    return cookies


def extract_ngrams(text, n=2, top_k=3):
    """提取文本中的 n-gram 高频片段"""
    if not text:
        return []
    grams = Counter()
    for length in range(n, n + 1):
        for i in range(len(text) - length + 1):
            chunk = text[i:i + length].strip()
            if chunk:
                grams[chunk] += 1
    return [w for w, _ in grams.most_common(top_k)]


# ============================================================
# 选题类型分类
# ============================================================

TYPE_MARKERS = {
    "技巧类": ["方法", "步骤", "公式", "模板", "技巧", "攻略", "指南", "提分", "套路", "拿分", "写出"],
    "概念类": ["定义", "什么是", "概念", "本质", "理解", "含义"],
    "现象类": ["焦虑", "内卷", "数字", "时代", "现象", "当下", "社会"],
    "思辨类": ["vs", "还是", "矛盾", "辩证", "对立", "关系", "权衡", "取舍"],
    "素材类": ["素材", "例子", "案例", "金句", "名言", "引用", "论据"],
    "范文类": ["范文", "满分", "一类文", "高分作文", "佳作", "考场作文"],
}


def classify_topic(title):
    """根据标题关键词分类帖子类型"""
    if not title:
        return "其他"
    for topic_type, markers in TYPE_MARKERS.items():
        for marker in markers:
            if marker in title:
                return topic_type
    return "其他"


# ============================================================
# API 搜索
# ============================================================

def search_notes_api(keyword, page=1, debug=False):
    """
    通过小红书搜索 API 获取笔记列表。
    返回笔记列表，None 表示签名错误需回退，空列表表示无结果或 cookie 过期。
    """
    url = "https://edith.xiaohongshu.com/api/sns/web/v1/search/notes"
    payload = {
        "keyword": keyword,
        "page": page,
        "page_size": config.SEARCH_NOTES_PER_PAGE,
        "sort": config.SEARCH_SORT,
        "note_type": 0,
    }

    for attempt in range(2):
        try:
            resp = requests.post(
                url,
                json=payload,
                headers=config.HEADERS,
                cookies=parse_cookies(config.COOKIES),
                timeout=15,
            )

            if resp.status_code == 429:
                print(f"    [限流] 等待30秒后重试...")
                time.sleep(30)
                continue

            resp.raise_for_status()
            data = resp.json()
            break
        except requests.RequestException as e:
            if attempt == 0:
                print(f"    [重试] 请求失败: {e}，5秒后重试...")
                time.sleep(5)
            else:
                print(f"    [错误] 请求失败: {e}")
                return []
    else:
        return []

    # 检查 API 错误
    if data.get("success") is False:
        msg = data.get("msg", "未知错误")
        print(f"    [错误] API 返回失败: {msg}")
        if "登录" in msg or "cookie" in msg.lower():
            print("    → Cookie 可能已过期，请重新获取")
            return []
        if "sign" in msg.lower() or "签名" in msg:
            print("    → 需要 x-s 签名，将尝试 Playwright 回退")
            return None  # 签名错误，触发回退
        return []

    if debug and page == 1:
        print("\n    [DEBUG] 原始 API 响应:")
        items = data.get("data", {}).get("items", [])
        if items:
            print(json.dumps(items[0], indent=2, ensure_ascii=False))
        print()

    items = data.get("data", {}).get("items", [])

    # API 成功但无 items（需要 x-s 签名才能获取搜索结果）
    if not items:
        if page == 1:
            print("    → API 返回空数据（可能需要 x-s 签名），将尝试 Playwright 回退")
            return None  # 触发回退
        return []  # 后续页面无更多结果

    notes = []
    for item in items:
        card = item.get("note_card", item)
        parsed = parse_search_note(card, keyword)
        if parsed:
            notes.append(parsed)

    return notes


def parse_search_note(card, keyword=""):
    """从搜索 API 返回的 note_card 中提取结构化数据"""
    try:
        note_id = card.get("note_id", "")

        # 标题
        title = (
            card.get("title", "")
            or card.get("display_title", "")
            or ""
        )

        # 互动数据
        interact = card.get("interact_info", {})
        if not isinstance(interact, dict):
            interact = {}

        likes = (
            card.get("liked_count", 0)
            or interact.get("liked_count", 0)
            or 0
        )
        comments = (
            card.get("comment_count", 0)
            or interact.get("comment_count", 0)
            or 0
        )
        favorites = (
            card.get("collected_count", 0)
            or interact.get("collected_count", 0)
            or 0
        )
        shares = (
            card.get("share_count", 0)
            or interact.get("share_count", 0)
            or 0
        )

        # 发布时间
        publish_ts = card.get("time", 0) or card.get("last_update_time", 0)
        publish_date = ""
        if publish_ts:
            try:
                publish_date = datetime.fromtimestamp(int(publish_ts) / 1000).strftime("%Y-%m-%d")
            except (ValueError, OSError):
                publish_date = ""

        # 笔记类型和描述
        note_type = card.get("type", "normal")
        desc = card.get("desc", "")

        # 作者信息
        user = card.get("user", {})
        author = user.get("nickname", "") if isinstance(user, dict) else ""

        note_url = f"https://www.xiaohongshu.com/explore/{note_id}"

        return {
            "note_id": note_id,
            "title": title,
            "likes": int(likes) if likes else 0,
            "comments": int(comments) if comments else 0,
            "favorites": int(favorites) if favorites else 0,
            "shares": int(shares) if shares else 0,
            "engagement": (int(likes) if likes else 0) + (int(favorites) if favorites else 0),
            "publish_date": publish_date,
            "note_type": note_type,
            "url": note_url,
            "desc": desc,
            "author": author,
            "keyword": keyword,
        }
    except Exception as e:
        print(f"    [警告] 解析笔记失败: {e}")
        return None


def search_by_api(keyword, debug=False):
    """搜索单个关键词，分页获取所有结果"""
    all_notes = []
    for page in range(1, config.SEARCH_MAX_PAGES + 1):
        print(f"    第{page}页...", end=" ", flush=True)
        notes = search_notes_api(keyword, page=page, debug=debug)

        # None = 签名错误，需要回退
        if notes is None:
            return None

        # 空列表 = 无更多结果
        if not notes:
            print("无更多结果")
            break

        all_notes.extend(notes)
        print(f"获取 {len(notes)} 条 (累计 {len(all_notes)} 条)")

        time.sleep(config.SEARCH_DELAY)

    return all_notes


# ============================================================
# Playwright 回退搜索
# ============================================================

def search_notes_playwright(keyword, debug=False):
    """通过 Playwright 浏览器自动化搜索小红书笔记"""
    if not HAS_PLAYWRIGHT:
        print("    [错误] Playwright 未安装。请运行:")
        print("    pip install playwright && playwright install chromium")
        return []

    print(f"    使用 Playwright 搜索...", flush=True)
    notes = []

    try:
        with sync_playwright() as p:
            # 优先使用系统 Chrome，无需下载 Chromium
            chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
            if os.path.exists(chrome_path):
                browser = p.chromium.launch(
                    headless=config.PLAYWRIGHT_HEADLESS,
                    executable_path=chrome_path,
                    args=["--disable-blink-features=AutomationControlled"],
                )
            else:
                browser = p.chromium.launch(
                    headless=config.PLAYWRIGHT_HEADLESS,
                    args=["--disable-blink-features=AutomationControlled"],
                )
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1440, "height": 900},
            )

            # 注入 cookie 保持登录状态
            cookies = parse_cookies(config.COOKIES)
            context_cookies = [
                {"name": k, "value": v, "domain": ".xiaohongshu.com", "path": "/"}
                for k, v in cookies.items()
            ]
            context.add_cookies(context_cookies)

            page = context.new_page()
            encoded_keyword = quote(keyword)
            search_url = (
                f"https://www.xiaohongshu.com/search_result"
                f"?keyword={encoded_keyword}&source=web_search_result_notes"
            )

            page.goto(search_url, timeout=config.PLAYWRIGHT_TIMEOUT)
            page.wait_for_load_state("networkidle")
            time.sleep(2)

            # 滚动加载更多结果
            scroll_count = min(config.SEARCH_MAX_PAGES, 10)
            for i in range(scroll_count):
                # 提取当前可见的笔记卡片
                cards = page.query_selector_all("section.note-item")
                if not cards:
                    cards = page.query_selector_all("[class*='note-item']")

                if debug and i == 0 and cards:
                    html = cards[0].inner_html()
                    print(f"\n    [DEBUG] 第一个卡片 HTML:\n{html[:500]}...\n")

                # 滚动
                page.evaluate("window.scrollBy(0, window.innerHeight)")
                time.sleep(random.uniform(1.5, 3.0))
                page.wait_for_load_state("networkidle", timeout=5000)

                print(f"    滚动 {i+1}/{scroll_count}...", flush=True)

            # 最终提取所有笔记
            cards = page.query_selector_all("section.note-item")
            if not cards:
                cards = page.query_selector_all("[class*='note-item']")

            seen_ids = set()
            for card in cards:
                try:
                    # 提取链接获取 note_id（取第一个 /explore/ 链接）
                    explore_link = card.query_selector("a[href*='/explore/']")
                    if not explore_link:
                        continue
                    href = explore_link.get_attribute("href") or ""

                    # 从 href 提取 note_id
                    note_id = ""
                    id_match = re.search(r"/explore/([a-f0-9]+)", href)
                    if id_match:
                        note_id = id_match.group(1)

                    if not note_id or note_id in seen_ids:
                        continue
                    seen_ids.add(note_id)

                    # 提取标题（.title 内的 span）
                    title_el = card.query_selector(".title span") or card.query_selector(".title")
                    title = title_el.inner_text().strip() if title_el else ""

                    # 提取点赞数（.like-wrapper 内的 .count）
                    like_el = card.query_selector(".like-wrapper .count") or card.query_selector(".like-wrapper")
                    likes_text = like_el.inner_text().strip() if like_el else "0"
                    likes = _parse_count(likes_text)

                    # 提取作者名（.name）
                    author_el = card.query_selector(".name")
                    author = author_el.inner_text().strip() if author_el else ""

                    # 提取时间（.time）
                    time_el = card.query_selector(".time")
                    publish_date = time_el.inner_text().strip() if time_el else ""

                    note_url = f"https://www.xiaohongshu.com/explore/{note_id}"

                    notes.append({
                        "note_id": note_id,
                        "title": title,
                        "likes": likes,
                        "comments": 0,
                        "favorites": 0,
                        "shares": 0,
                        "engagement": likes,
                        "publish_date": publish_date,
                        "note_type": "normal",
                        "url": note_url,
                        "desc": "",
                        "author": author,
                        "keyword": keyword,
                    })
                except Exception:
                    continue

            browser.close()

    except Exception as e:
        print(f"    [错误] Playwright 执行失败: {e}")
        return []

    print(f"    Playwright 共获取 {len(notes)} 条笔记")
    return notes


def _parse_count(text):
    """解析 '1.2万' '3456' 等格式的数字"""
    if not text:
        return 0
    text = text.strip().replace(",", "")
    try:
        if "万" in text:
            return int(float(text.replace("万", "")) * 10000)
        return int(re.sub(r"[^\d]", "", text) or "0")
    except (ValueError, TypeError):
        return 0


# ============================================================
# 搜索调度：API 优先，失败回退 Playwright
# ============================================================

def search_notes(keyword, debug=False):
    """统一搜索入口：先尝试 API，签名失败则回退 Playwright。
    返回 (notes_list, used_playwright)"""
    print(f"  搜索关键词: \"{keyword}\"")

    notes = search_by_api(keyword, debug=debug)

    # None = 签名错误，需要回退
    if notes is None:
        if config.USE_PLAYWRIGHT_FALLBACK:
            print(f"  → API 签名失败，切换到 Playwright 回退")
            notes = search_notes_playwright(keyword, debug=debug)
            return notes, True
        else:
            print(f"  → API 签名失败，跳过。启用 Playwright 回退请设置 USE_PLAYWRIGHT_FALLBACK=True")
            notes = []

    return notes, False


# ============================================================
# 选题分析
# ============================================================

def extract_imitable_topics(notes, top_n=15):
    """
    按标题关键词聚类帖子，排名互动量，提取可借鉴选题。
    """
    if not notes:
        return []

    # 去重（同一 note_id 可能被多个关键词搜到）
    seen = {}
    for n in notes:
        nid = n.get("note_id", "")
        if nid and nid not in seen:
            seen[nid] = n
    unique_notes = list(seen.values())

    # 按标题相似度聚类
    clusters = {}
    for note in unique_notes:
        title = note.get("title", "")
        if not title:
            continue
        grams = extract_ngrams(title, n=2, top_k=3)
        if not grams:
            continue
        key = frozenset(grams)
        clusters.setdefault(key, []).append(note)

    # 按集群总互动量排序
    ranked = sorted(
        clusters.values(),
        key=lambda group: sum(n["engagement"] for n in group),
        reverse=True,
    )

    topics = []
    for group in ranked[:top_n]:
        best = max(group, key=lambda n: n["engagement"])
        topic_type = classify_topic(best["title"])

        # 生成创作建议
        suggestion = _generate_suggestion(best, group, topic_type)

        topics.append({
            "title": best["title"],
            "url": best["url"],
            "engagement": best["engagement"],
            "cluster_size": len(group),
            "type": topic_type,
            "desc": best.get("desc", ""),
            "author": best.get("author", ""),
            "suggestion": suggestion,
            "likes": best["likes"],
            "favorites": best["favorites"],
            "comments": best["comments"],
        })

    return topics


def _generate_suggestion(best, cluster, topic_type):
    """基于帖子类型和集群特征生成创作建议"""
    title = best.get("title", "")
    cluster_size = len(cluster)

    # 根据类型生成不同建议
    type_suggestions = {
        "技巧类": "可用「破题三步法」或「八段式框架」重新切入，加入具体真题演示",
        "概念类": "从核心概念的思辨关系入手，用「苏格拉底式提问」引导读者深入思考",
        "现象类": "结合当下热点现象，从辩证角度分析，给出作文中的运用方法",
        "思辨类": "用「感性→理性→知性」三元结构展开，加入正反论据对比",
        "素材类": "精选3-5个素材，给出具体适用的作文题目和论证角度",
        "范文类": "从得分点拆解入手，标注可模仿的句式和结构亮点",
    }

    base = type_suggestions.get(topic_type, "从不同角度重新解读，加入独特见解")

    if cluster_size >= 5:
        base = f"该方向有{cluster_size}篇同类帖子（需求旺盛），" + base
    elif cluster_size >= 2:
        base = f"有{cluster_size}篇类似帖子，" + base

    return base


# ============================================================
# 关键词统计
# ============================================================

def compute_keyword_stats(all_notes):
    """从所有搜索结果中提取高频关键词"""
    stop_words = {
        "的", "了", "是", "在", "和", "也", "有", "就", "不", "都",
        "一", "到", "把", "被", "让", "给", "从", "这", "那", "你",
        "我", "他", "她", "它", "们", "会", "能", "要", "好", "很",
        "什么", "怎么", "为什么", "如何", "怎样", "可以", "没有",
        "还是", "一个", "这种", "那种", "不是", "这个", "那个",
        "一下", "一些", "一直", "一样", "一起", "因为", "所以",
    }

    word_counts = Counter()
    for note in all_notes:
        title = note.get("title", "")
        if not title:
            continue
        for length in range(2, 5):
            for i in range(len(title) - length + 1):
                chunk = title[i:i + length]
                if chunk.strip() and chunk not in stop_words:
                    word_counts[chunk] += 1

    return word_counts.most_common(20)


# ============================================================
# 报告生成
# ============================================================

def generate_report(keyword_results, all_notes, method="API"):
    """生成 Markdown 选题报告"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    keywords_used = list(keyword_results.keys())

    lines = [
        "# 小红书搜索选题报告",
        "",
        f"> 生成时间: {now}",
        f"> 搜索关键词: {', '.join(keywords_used)}",
        f"> 数据来源: {'小红书搜索 API' if method == 'API' else 'Playwright 浏览器自动化'}",
        "",
    ]

    # 搜索概览
    engagements = [n["engagement"] for n in all_notes]
    lines.extend([
        "## 搜索概览",
        "",
        "| 指标 | 数值 |",
        "|------|------|",
        f"| 搜索关键词数 | {len(keywords_used)} |",
        f"| 获取笔记总数 | {len(all_notes)} |",
        f"| 最高互动 | {max(engagements):,} |" if engagements else "| 最高互动 | 0 |",
        f"| 平均互动 | {sum(engagements) / len(engagements):.0f} |" if engagements else "| 平均互动 | 0 |",
        "",
    ])

    # 可借鉴选题 Top
    topics = extract_imitable_topics(all_notes, top_n=15)
    if topics:
        lines.extend([
            f"## 可借鉴选题 Top {len(topics)}",
            "",
            "| 排名 | 选题方向 | 代表帖子 | 互动量 | 同类帖子数 | 类型 |",
            "|------|----------|----------|--------|------------|------|",
        ])
        for i, t in enumerate(topics, 1):
            title = t["title"][:25] + ("..." if len(t["title"]) > 25 else "")
            lines.append(
                f"| {i} | {title} | [{title}]({t['url']}) | "
                f"{t['engagement']:,} | {t['cluster_size']} | {t['type']} |"
            )
        lines.append("")

    # 选题详情与创作建议
    if topics:
        lines.extend(["## 选题详情与创作建议", ""])
        for i, t in enumerate(topics, 1):
            lines.extend([
                f"### {i}. {t['title']} (互动: {t['engagement']:,})",
                "",
                f"- **代表帖子**: [{t['title']}]({t['url']})",
            ])
            if t.get("author"):
                lines.append(f"- **作者**: {t['author']}")
            if t.get("desc"):
                desc_preview = t["desc"][:100] + ("..." if len(t["desc"]) > 100 else "")
                lines.append(f"- **内容摘要**: {desc_preview}")
            lines.extend([
                f"- **同类帖子数**: {t['cluster_size']} 篇",
                f"- **类型**: {t['type']}",
                f"- **互动数据**: 点赞 {t['likes']:,} | 收藏 {t['favorites']:,} | 评论 {t['comments']:,}",
                f"- **创作建议**: {t['suggestion']}",
                "",
            ])

    # 高频关键词
    kw_stats = compute_keyword_stats(all_notes)
    if kw_stats:
        lines.extend(["## 高频关键词", "", "| 关键词 | 出现次数 |", "|--------|----------|"])
        for word, count in kw_stats[:15]:
            lines.append(f"| {word} | {count} |")
        lines.append("")

    # 各关键词搜索结果分布
    lines.extend(["## 各关键词搜索结果分布", ""])
    for keyword, notes in keyword_results.items():
        lines.extend([
            f"### \"{keyword}\"",
            "",
            f"共获取 {len(notes)} 条笔记",
            "",
        ])
        if notes:
            sorted_notes = sorted(notes, key=lambda x: x["engagement"], reverse=True)
            lines.extend([
                "| 排名 | 标题 | 点赞 | 收藏 | 总互动 | 日期 |",
                "|------|------|------|------|--------|------|",
            ])
            for i, n in enumerate(sorted_notes[:20], 1):
                title = n["title"][:30] + ("..." if len(n["title"]) > 30 else "")
                lines.append(
                    f"| {i} | [{title}]({n['url']}) | {n['likes']:,} | "
                    f"{n['favorites']:,} | {n['engagement']:,} | {n['publish_date']} |"
                )
            lines.append("")

    lines.extend([
        "---",
        "",
        "*此报告由 xhs_search_topics.py 自动生成。*",
    ])

    return "\n".join(lines)


def inject_llm_suggestions(report, llm_text):
    """将 LLM 生成的选题建议插入报告中，放在选题详情之后、高频关键词之前"""
    marker = "## 高频关键词"
    if marker in report:
        llm_section = "\n## AI 选题建议（MiMo 生成）\n\n" + llm_text + "\n\n"
        report = report.replace(marker, llm_section + marker)
    else:
        # 如果没有高频关键词部分，插入到末尾
        report += "\n\n## AI 选题建议（MiMo 生成）\n\n" + llm_text + "\n"
    return report


# ============================================================
# MiMo LLM 选题建议
# ============================================================

def call_mimo_suggestions(notes):
    """调用 MiMo API，基于搜索结果帖子生成选题建议"""
    if not notes:
        return ""

    # 按互动量取 Top 15 帖子作为输入
    top_notes = sorted(notes, key=lambda x: x["engagement"], reverse=True)[:15]

    # 构造帖子摘要
    posts_summary = []
    for i, n in enumerate(top_notes, 1):
        title = n.get("title", "")
        desc = n.get("desc", "")
        likes = n.get("likes", 0)
        author = n.get("author", "")
        post_type = n.get("type", "")
        line = f"{i}. 「{title}」"
        if author:
            line += f"（作者：{author}）"
        line += f" - 点赞 {likes:,}"
        if desc:
            desc_short = desc[:80]
            line += f"\n   内容：{desc_short}"
        posts_summary.append(line)

    posts_text = "\n".join(posts_summary)

    prompt = f"""你是一位上海高考作文写作领域的资深老师，运营小红书账号"上海思辨写作云老师"。

以下是小红书上关于"高考作文思辨写作"的热门帖子（按互动量排序）：

{posts_text}

请基于以上热门帖子，给出5个可操作的选题建议。要求：
1. 分析这些帖子为什么受欢迎（标题/内容角度）
2. 针对每个建议给出具体的内容切入角度
3. 考虑到你的账号定位是上海高考思辨写作教学，建议要有差异化
4. 用中文回答，格式清晰"""

    print("  调用 MiMo 生成选题建议...", flush=True)

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.MIMO_API_KEY}",
    }
    payload = {
        "model": config.MIMO_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": config.MIMO_TEMPERATURE,
        "max_tokens": config.MIMO_MAX_TOKENS,
    }

    try:
        resp = requests.post(
            config.MIMO_API_URL,
            json=payload,
            headers=headers,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()

        if "choices" in data and data["choices"]:
            content = data["choices"][0].get("message", {}).get("content", "")
            print("  MiMo 选题建议生成完成")
            return content
        else:
            error = data.get("error", {}).get("message", "未知错误")
            print(f"  [警告] MiMo 返回异常: {error}")
            return ""

    except requests.RequestException as e:
        print(f"  [警告] MiMo API 调用失败: {e}")
        return ""


# ============================================================
# CLI 入口
# ============================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="小红书搜索选题脚本")
    parser.add_argument(
        "--keyword", type=str, default=None,
        help="自定义搜索关键词（覆盖 config 中的配置）",
    )
    parser.add_argument(
        "--sort", choices=["general", "hot", "new"], default=None,
        help="排序方式: general=综合, hot=最热, new=最新",
    )
    parser.add_argument(
        "--debug", action="store_true", help="调试模式：打印原始 API 响应",
    )
    args = parser.parse_args()

    # 覆盖配置
    if args.sort:
        config.SEARCH_SORT = args.sort

    # Cookie 校验
    if not config.COOKIES.strip():
        print("=" * 50)
        print("错误: Cookie 未配置！")
        print("=" * 50)
        print()
        print("请先在 scripts/config.py 中配置小红书 Cookie。")
        print("详见 scripts/README_scraper.md 获取 Cookie 的方法。")
        sys.exit(1)

    # 确定搜索关键词
    if args.keyword:
        keywords = [args.keyword]
    else:
        keywords = config.SEARCH_KEYWORDS

    if not keywords:
        print("错误: 未配置搜索关键词。请在 config.py 中设置 SEARCH_KEYWORDS。")
        sys.exit(1)

    print("=" * 50)
    print("小红书搜索选题脚本")
    print("=" * 50)
    print(f"关键词: {', '.join(keywords)}")
    print(f"排序方式: {config.SEARCH_SORT}")
    print()

    # 逐关键词搜索
    keyword_results = {}
    all_notes = []
    method = "API"

    for kw in keywords:
        notes, used_pw = search_notes(kw, debug=args.debug)
        if used_pw:
            method = "Playwright"
        keyword_results[kw] = notes
        all_notes.extend(notes)
        print()

    if not all_notes:
        print("未获取到任何笔记数据。")
        print("可能原因: Cookie 过期、关键词无结果、或需要 x-s 签名。")
        sys.exit(1)

    # 生成报告
    report = generate_report(keyword_results, all_notes, method=method)

    # 调用 MiMo 生成选题建议
    llm_suggestions = call_mimo_suggestions(all_notes)
    if llm_suggestions:
        report = inject_llm_suggestions(report, llm_suggestions)

    # 保存报告
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)
    report_dir = os.path.join(project_dir, config.REPORT_DIR)
    os.makedirs(report_dir, exist_ok=True)

    date_str = datetime.now().strftime("%Y%m%d")
    filename = f"search_topics_{date_str}.md"
    filepath = os.path.join(report_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(report)

    print("=" * 50)
    print(f"报告已保存: {filepath}")
    print(f"共分析 {len(all_notes)} 条笔记")
    print(f"提取 {len(extract_imitable_topics(all_notes))} 个可借鉴选题")


if __name__ == "__main__":
    main()
