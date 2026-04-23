# -*- coding: utf-8 -*-
"""
小红书博主内容爬虫 & 互动分析脚本
用法: python scripts/xhs_scraper.py [--debug] [--account own|competitor|all]
"""

import json
import time
import os
import sys
from datetime import datetime
from collections import Counter

import requests

# 加载同目录下的 config
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config


# ============================================================
# Cookie 解析
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


# ============================================================
# 爬取核心
# ============================================================

def fetch_user_notes(user_id, account_name, debug=False):
    """通过小红书网页 API 拉取指定用户的所有笔记"""
    url = "https://edith.xiaohongshu.com/api/sns/web/v1/user_posted"
    all_notes = []
    cursor = ""
    page = 0

    while page < config.MAX_PAGES:
        page += 1
        params = {
            "num": config.NOTES_PER_PAGE,
            "cursor": cursor,
            "user_id": user_id,
        }

        data = None
        for attempt in range(2):  # 最多重试一次
            try:
                resp = requests.get(
                    url,
                    params=params,
                    headers=config.HEADERS,
                    cookies=parse_cookies(config.COOKIES),
                    timeout=15,
                )

                if resp.status_code == 429:
                    print(f"  [限流] 等待30秒后重试...")
                    time.sleep(30)
                    continue

                resp.raise_for_status()
                data = resp.json()
                break
            except requests.RequestException as e:
                if attempt == 0:
                    print(f"  [重试] 请求失败: {e}，5秒后重试...")
                    time.sleep(5)
                else:
                    print(f"  [错误] 请求失败 (第{page}页): {e}")
                    break
        else:
            break

        if data is None:
            break

        # 检查 API 错误
        if data.get("success") is False:
            msg = data.get("msg", "未知错误")
            print(f"  [错误] API 返回失败: {msg}")
            if "登录" in msg or "cookie" in msg.lower():
                print("  → Cookie 可能已过期，请重新获取")
            if "sign" in msg.lower() or "签名" in msg:
                print("  → 需要 x-s 签名，请从浏览器 Network 面板复制 x-s 和 x-t")
            break

        notes_data = data.get("data", {})
        notes = notes_data.get("notes", [])

        if debug and page == 1 and notes:
            print("\n  [DEBUG] 原始 API 响应 (第一条笔记):")
            print(json.dumps(notes[0], indent=2, ensure_ascii=False))
            print()

        if not notes:
            print(f"  第{page}页无更多笔记，爬取完成")
            break

        for note in notes:
            parsed = parse_note(note)
            if parsed:
                parsed["account_name"] = account_name
                all_notes.append(parsed)

        cursor = notes_data.get("cursor", "")
        has_more = notes_data.get("has_more", False)

        print(f"  第{page}页: 获取 {len(notes)} 条笔记 (累计 {len(all_notes)} 条)")

        if not has_more or not cursor:
            break

        time.sleep(config.REQUEST_DELAY)

    return all_notes


def parse_note(note):
    """从 API 返回的单条笔记中提取结构化数据"""
    try:
        note_id = note.get("note_id", "")

        # 标题：尝试多个可能的字段
        title = (
            note.get("title", "")
            or note.get("display_title", "")
            or ""
        )
        if not title:
            card = note.get("note_card", {})
            if isinstance(card, dict):
                title = card.get("title", "")

        # 互动数据：字段名可能因版本不同而变化
        interact = note.get("interact_info", {})
        if not isinstance(interact, dict):
            interact = {}

        likes = (
            note.get("liked_count", 0)
            or interact.get("liked_count", 0)
            or 0
        )
        comments = (
            note.get("comment_count", 0)
            or interact.get("comment_count", 0)
            or 0
        )
        favorites = (
            note.get("collected_count", 0)
            or interact.get("collected_count", 0)
            or 0
        )
        shares = (
            note.get("share_count", 0)
            or interact.get("share_count", 0)
            or 0
        )

        # 发布时间
        publish_ts = note.get("time", 0) or note.get("last_update_time", 0)
        publish_date = ""
        if publish_ts:
            try:
                publish_date = datetime.fromtimestamp(int(publish_ts) / 1000).strftime("%Y-%m-%d")
            except (ValueError, OSError):
                publish_date = ""

        # 笔记类型
        note_type = note.get("type", "normal")

        # URL
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
        }
    except Exception as e:
        print(f"  [警告] 解析笔记失败: {e}")
        return None


# ============================================================
# 数据分析
# ============================================================

def analyze_notes(notes):
    """对笔记列表进行互动分析"""
    if not notes:
        return {"top_notes": [], "patterns": {}, "summary": {}}

    # 按总互动量排序
    sorted_notes = sorted(notes, key=lambda x: x["engagement"], reverse=True)
    top_notes = sorted_notes[: config.TOP_N]

    # 标题关键词提取
    high_engagement = [n for n in sorted_notes if n["engagement"] > 0][:30]
    title_keywords = extract_title_patterns(high_engagement)

    # 内容形式分析
    type_performance = {}
    for n in notes:
        nt = n["note_type"]
        if nt not in type_performance:
            type_performance[nt] = {"count": 0, "total_engagement": 0}
        type_performance[nt]["count"] += 1
        type_performance[nt]["total_engagement"] += n["engagement"]

    # 汇总统计
    engagements = [n["engagement"] for n in notes]
    engagements_sorted = sorted(engagements)
    mid = len(engagements_sorted) // 2
    summary = {
        "total_posts": len(notes),
        "total_engagement": sum(engagements),
        "avg_engagement": sum(engagements) / len(engagements) if engagements else 0,
        "max_engagement": max(engagements) if engagements else 0,
        "median_engagement": engagements_sorted[mid] if engagements else 0,
    }

    return {
        "top_notes": top_notes,
        "patterns": {
            "title_keywords": title_keywords,
            "type_performance": type_performance,
        },
        "summary": summary,
    }


def extract_title_patterns(notes):
    """从高互动帖子标题中提取高频关键词（2-4字片段）"""
    stop_words = {
        "的", "了", "是", "在", "和", "也", "有", "就", "不", "都",
        "一", "到", "把", "被", "让", "给", "从", "这", "那", "你",
        "我", "他", "她", "它", "们", "会", "能", "要", "好", "很",
        "什么", "怎么", "为什么", "如何", "怎样", "可以", "没有",
        "还是", "一个", "这种", "那种", "不是", "这个", "那个",
    }

    word_counts = Counter()
    for note in notes:
        title = note.get("title", "")
        if not title:
            continue
        for length in range(2, 5):
            for i in range(len(title) - length + 1):
                chunk = title[i : i + length]
                if chunk.strip() and chunk not in stop_words:
                    word_counts[chunk] += 1

    return word_counts.most_common(20)


# ============================================================
# 报告生成
# ============================================================

def generate_report(all_results):
    """生成 Markdown 分析报告"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = [
        "# 小红书博主内容分析报告",
        "",
        f"> 生成时间: {now}",
        "",
    ]

    account_keys = list(all_results.keys())

    # 每个账号的分析
    for key in account_keys:
        r = all_results[key]
        name = r.get("account_name", key)
        lines.extend(_section_account(name, r["analysis"]))

    # 跨账号对比
    if len(account_keys) >= 2:
        lines.extend(
            _section_comparison(
                all_results[account_keys[0]]["analysis"],
                all_results[account_keys[1]]["analysis"],
                all_results[account_keys[0]].get("account_name", account_keys[0]),
                all_results[account_keys[1]].get("account_name", account_keys[1]),
            )
        )

    # 选题建议
    lines.extend(_section_suggestions(all_results))

    lines.extend([
        "",
        "---",
        "",
        "*此报告由 xhs_scraper.py 自动生成，数据来源于小红书网页版 API。*",
    ])

    return "\n".join(lines)


def _section_account(name, analysis):
    """单个账号的报告段落"""
    s = analysis["summary"]
    lines = [
        f"## {name}",
        "",
        "| 指标 | 数值 |",
        "|------|------|",
        f"| 总笔记数 | {s['total_posts']} |",
        f"| 总互动量 | {s['total_engagement']:,} |",
        f"| 平均互动 | {s['avg_engagement']:.0f} |",
        f"| 最高互动 | {s['max_engagement']:,} |",
        f"| 中位互动 | {s['median_engagement']:,} |",
        "",
    ]

    # 高互动帖子表格
    top = analysis.get("top_notes", [])
    if top:
        lines.extend([
            f"### 高互动帖子 Top {len(top)}",
            "",
            "| 排名 | 标题 | 点赞 | 收藏 | 评论 | 总互动 | 日期 |",
            "|------|------|------|------|------|--------|------|",
        ])
        for i, n in enumerate(top, 1):
            title = n["title"][:30] + ("..." if len(n["title"]) > 30 else "")
            lines.append(
                f"| {i} | [{title}]({n['url']}) | {n['likes']:,} | "
                f"{n['favorites']:,} | {n['comments']:,} | "
                f"{n['engagement']:,} | {n['publish_date']} |"
            )
        lines.append("")

    # 标题关键词
    keywords = analysis.get("patterns", {}).get("title_keywords", [])
    if keywords:
        lines.extend(["### 高互动帖子标题关键词", ""])
        lines.append("| 关键词 | 出现次数 |")
        lines.append("|--------|----------|")
        for word, count in keywords[:15]:
            lines.append(f"| {word} | {count} |")
        lines.append("")

    # 内容形式
    type_perf = analysis.get("patterns", {}).get("type_performance", {})
    if type_perf:
        lines.extend(["### 内容形式表现", ""])
        lines.append("| 形式 | 数量 | 平均互动 |")
        lines.append("|------|------|----------|")
        for nt, info in type_perf.items():
            avg = info["total_engagement"] / info["count"] if info["count"] else 0
            label = "图文" if nt == "normal" else "视频" if nt == "video" else nt
            lines.append(f"| {label} | {info['count']} | {avg:.0f} |")
        lines.append("")

    return lines


def _section_comparison(own_a, comp_a, own_name, comp_name):
    """跨账号对比段落"""
    return [
        "## 账号对比",
        "",
        f"| 指标 | {own_name} | {comp_name} |",
        "|------|------|------|",
        f"| 笔记数 | {own_a['summary']['total_posts']} | {comp_a['summary']['total_posts']} |",
        f"| 平均互动 | {own_a['summary']['avg_engagement']:.0f} | {comp_a['summary']['avg_engagement']:.0f} |",
        f"| 最高互动 | {own_a['summary']['max_engagement']:,} | {comp_a['summary']['max_engagement']:,} |",
        f"| 总互动 | {own_a['summary']['total_engagement']:,} | {comp_a['summary']['total_engagement']:,} |",
        "",
    ]


def _section_suggestions(all_results):
    """选题建议段落"""
    # 收集所有账号的高互动关键词
    all_keywords = {}
    for key, r in all_results.items():
        kw_list = r["analysis"].get("patterns", {}).get("title_keywords", [])
        name = r.get("account_name", key)
        all_keywords[name] = set(k for k, _ in kw_list[:10])

    lines = [
        "## 选题建议",
        "",
    ]

    # 如果有两个账号，做交叉分析
    names = list(all_keywords.keys())
    if len(names) >= 2:
        shared = all_keywords[names[0]] & all_keywords[names[1]]
        comp_only = all_keywords[names[1]] - all_keywords[names[0]]

        if shared:
            lines.extend(["### 共同高互动话题（已验证有效）", ""])
            for kw in shared:
                lines.append(f"- **{kw}** — 双方都获得高互动，值得深入创作")
            lines.append("")

        if comp_only:
            lines.extend([f"### 竞品高互动话题（可借鉴）", ""])
            for kw in comp_only:
                lines.append(f"- **{kw}** — 竞品的高互动话题，评估是否适合你的定位")
            lines.append("")

    # 基于 Top 帖子的具体建议
    for key, r in all_results.items():
        name = r.get("account_name", key)
        top = r["analysis"].get("top_notes", [])[:5]
        if top:
            lines.extend([f"### {name} 高互动帖子选题灵感", ""])
            for i, n in enumerate(top, 1):
                lines.append(f"{i}. **{n['title']}** (互动: {n['engagement']:,})")
                lines.append(f"   → 可从「破题三步法」或「八段式」角度重新切入")
            lines.append("")

    return lines


# ============================================================
# CLI 入口
# ============================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="小红书博主内容分析爬虫")
    parser.add_argument(
        "--debug", action="store_true", help="调试模式：打印原始 API 响应"
    )
    parser.add_argument(
        "--account",
        choices=["own", "competitor", "all"],
        default="all",
        help="指定爬取哪个账号",
    )
    args = parser.parse_args()

    # Cookie 校验
    if not config.COOKIES.strip():
        print("=" * 50)
        print("错误: Cookie 未配置！")
        print("=" * 50)
        print()
        print("请按以下步骤获取 Cookie：")
        print("1. 用 Chrome 浏览器打开 https://www.xiaohongshu.com 并登录")
        print("2. 按 F12 打开开发者工具")
        print("3. 切换到 Network 标签")
        print("4. 刷新页面 (Cmd+R)")
        print("5. 点击任意一个发往 xiaohongshu.com 的请求")
        print("6. 在 Request Headers 中找到 'cookie:' 行")
        print("7. 复制整个 cookie 值")
        print("8. 粘贴到 scripts/config.py 中的 COOKIES 变量")
        print()
        print("然后重新运行此脚本。")
        sys.exit(1)

    # 确定爬取目标
    if args.account == "all":
        targets = list(config.ACCOUNTS.items())
    else:
        targets = [(args.account, config.ACCOUNTS[args.account])]

    all_results = {}
    for key, account in targets:
        print(f"\n正在爬取: {account['name']} ({account['user_id']})")
        notes = fetch_user_notes(account["user_id"], account["name"], debug=args.debug)
        print(f"  共获取 {len(notes)} 条笔记")

        analysis = analyze_notes(notes)
        all_results[key] = {
            "notes": notes,
            "analysis": analysis,
            "account_name": account["name"],
        }

    if not all_results:
        print("无数据可分析")
        sys.exit(1)

    # 生成报告
    report = generate_report(all_results)

    # 保存报告
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)
    report_dir = os.path.join(project_dir, config.REPORT_DIR)
    os.makedirs(report_dir, exist_ok=True)

    date_str = datetime.now().strftime("%Y%m%d")
    filename = f"engagement_report_{date_str}.md"
    filepath = os.path.join(report_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(report)

    total = sum(len(r["notes"]) for r in all_results.values())
    print(f"\n报告已保存: {filepath}")
    print(f"共分析 {total} 条笔记")


if __name__ == "__main__":
    main()
