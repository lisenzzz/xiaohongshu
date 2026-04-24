# -*- coding: utf-8 -*-
"""
PDF处理流水线：提取 → 纠错 → 保存为Markdown
用法:
  python -m scripts.pipeline.pdf_pipeline --dry-run          # 仅提取，不纠错
  python -m scripts.pipeline.pdf_pipeline --skip-correct      # 跳过纠错，直接保存
  python -m scripts.pipeline.pdf_pipeline --pdf 01            # 只处理指定PDF
  python -m scripts.pipeline.pdf_pipeline                     # 完整流程
"""

import os
import sys
import json
import re
import argparse
from datetime import datetime

from .pdf_extract import extract_pdf_text
from .mimo_correct import chunk_text, correct_text_batch

# PDF编号 → 分类映射
PDF_CATEGORIES = {
    "01": ("frameworks", "材料分类"),
    "02": ("frameworks", "辩证分析"),
    "03": ("frameworks", "哲学思辨关系"),
    "04": ("frameworks", "母题"),
    "05": ("frameworks", "八段式框架"),
    "06": ("frameworks", "概念界定"),
    "07": ("frameworks", "概念类作文"),
    "08": ("frameworks", "比喻类作文"),
    "09": ("frameworks", "一类文特征"),
    "10": ("frameworks", "两个关键词"),
    "11": ("frameworks", "非对立关键词"),
    "12": ("frameworks", "三个关键词"),
    "13": ("frameworks", "四个关键词"),
    "14": ("frameworks", "选择型作文"),
    "15": ("frameworks", "论证段展开"),
    "16": ("materials", "美学与艺术"),
    "17": ("materials", "刘擎西方思想"),
    "18": ("frameworks", "开头结尾"),
    "19": ("materials", "课本素材"),
    "20": ("materials", "哲理句子"),
    "21": ("materials", "理论论据"),
}

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
PDF_DIR = os.path.join(PROJECT_ROOT, "assets/references")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "knowledge")


def extract_title(filename: str) -> str:
    """从文件名提取标题"""
    match = re.search(r"云老师作文专题(.+?)——(.+?)\.pdf", filename)
    if match:
        return match.group(2)
    return filename.replace(".pdf", "")


def format_as_markdown(title: str, num: str, source_file: str, content: str, page_count: int) -> str:
    """将内容格式化为Markdown"""
    return f"""# 专题{num}：{title}

> 来源: {source_file}
> 处理日期: {datetime.now().strftime('%Y-%m-%d')}
> 原始页数: {page_count}
> 校对状态: LLM校对

---

{content}
"""


def run_pipeline(pdf_dir: str = PDF_DIR, output_dir: str = OUTPUT_DIR,
                 skip_correct: bool = False, dry_run: bool = False,
                 target_pdf: str = None):
    """运行PDF处理流水线"""
    pdf_files = sorted([f for f in os.listdir(pdf_dir) if f.endswith(".pdf")])
    if target_pdf:
        pdf_files = [f for f in pdf_files if f[:2] == target_pdf]

    results = []
    for pdf_file in pdf_files:
        num = pdf_file[:2]
        if num not in PDF_CATEGORIES:
            print(f"[SKIP] {pdf_file}: 未在分类映射中")
            continue

        category, short_title = PDF_CATEGORIES[num]
        pdf_path = os.path.join(pdf_dir, pdf_file)

        print(f"\n[处理] {pdf_file}")

        # Step 1: 提取
        pages = extract_pdf_text(pdf_path)
        page_count = len(pages)
        raw_text = "\n\n".join(p["text"] for p in pages if p["char_count"] > 10)
        total_chars = len(raw_text)

        if not raw_text.strip():
            print(f"  [WARN] 未提取到文本，可能是扫描版PDF")
            results.append({"file": pdf_file, "status": "no_text", "chars": 0})
            continue

        print(f"  提取: {page_count}页, {total_chars}字")

        if dry_run:
            results.append({"file": pdf_file, "status": "dry_run", "chars": total_chars, "pages": page_count})
            continue

        # Step 2: 纠错
        if not skip_correct:
            chunks = chunk_text(raw_text, max_chars=2500)
            print(f"  切分为 {len(chunks)} 个块，开始LLM纠错...")
            corrected_chunks = correct_text_batch(chunks)
            final_text = "\n\n".join(corrected_chunks)
        else:
            final_text = raw_text

        # Step 3: 保存
        title = extract_title(pdf_file)
        md_content = format_as_markdown(title, num, pdf_file, final_text, page_count)

        out_category_dir = os.path.join(output_dir, category)
        os.makedirs(out_category_dir, exist_ok=True)
        output_path = os.path.join(out_category_dir, f"{num}-{short_title}.md")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        print(f"  保存: {output_path} ({len(final_text)}字)")
        results.append({
            "file": pdf_file,
            "status": "ok",
            "output": output_path,
            "chars": len(final_text),
            "pages": page_count,
            "category": category,
        })

    return results


def generate_metadata(results: list, output_dir: str):
    """生成knowledge/metadata.json"""
    entries = []
    for r in results:
        if r["status"] != "ok":
            continue
        num = r["file"][:2]
        _, short_title = PDF_CATEGORIES.get(num, ("unknown", "unknown"))
        entries.append({
            "id": f"pdf-{num}",
            "title": short_title,
            "source": f"assets/references/{r['file']}",
            "output": r["output"].replace(PROJECT_ROOT + "/", ""),
            "category": r["category"],
            "char_count": r["chars"],
            "pages": r["pages"],
            "processed_date": datetime.now().strftime("%Y-%m-%d"),
            "correction_status": "llm_corrected",
            "chroma_collection": r["category"],
        })

    metadata = {
        "version": "1.0",
        "last_updated": datetime.now().isoformat(),
        "entries": entries,
    }

    meta_path = os.path.join(output_dir, "metadata.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    print(f"\n元数据已保存: {meta_path} ({len(entries)}个条目)")
    return metadata


def main():
    parser = argparse.ArgumentParser(description="PDF知识提取流水线")
    parser.add_argument("--dry-run", action="store_true", help="仅提取，不纠错不保存")
    parser.add_argument("--skip-correct", action="store_true", help="跳过LLM纠错")
    parser.add_argument("--pdf", type=str, help="只处理指定编号的PDF（如 01）")
    parser.add_argument("--pdf-dir", type=str, default=PDF_DIR, help="PDF目录")
    parser.add_argument("--output-dir", type=str, default=OUTPUT_DIR, help="输出目录")
    args = parser.parse_args()

    results = run_pipeline(
        pdf_dir=args.pdf_dir,
        output_dir=args.output_dir,
        skip_correct=args.skip_correct,
        dry_run=args.dry_run,
        target_pdf=args.pdf,
    )

    if not args.dry_run:
        generate_metadata(results, args.output_dir)

    # 打印汇总
    print("\n" + "=" * 50)
    print("处理汇总:")
    for r in results:
        status_icon = {"ok": "✓", "dry_run": "○", "no_text": "✗"}.get(r["status"], "?")
        print(f"  {status_icon} {r['file']}: {r['status']} ({r['chars']}字)")


if __name__ == "__main__":
    main()
