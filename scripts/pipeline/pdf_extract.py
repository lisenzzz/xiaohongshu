# -*- coding: utf-8 -*-
"""PDF文本提取模块 - 使用PyMuPDF，支持OCR回退"""

import os
import fitz  # PyMuPDF


def extract_page_text(page) -> str:
    """从单页提取文本，优先使用文本层，空则回退OCR"""
    blocks = page.get_text("blocks")
    text_blocks = [b[4].strip() for b in blocks if b[6] == 0 and b[4].strip()]
    combined = "\n".join(text_blocks)

    # 如果文本层为空或极少，尝试OCR
    if len(combined.strip()) < 20:
        try:
            tp = page.get_textpage_ocr(language="chi_sim+eng", dpi=300, full=True)
            ocr_text = page.get_text("text", textpage=tp)
            if len(ocr_text.strip()) > len(combined.strip()):
                combined = ocr_text.strip()
        except Exception:
            pass  # OCR失败则保留原始提取结果

    return combined


def extract_pdf_text(pdf_path: str) -> list:
    """
    按页提取PDF文本，自动对扫描页使用OCR。
    返回: [{"page": int, "text": str, "char_count": int}, ...]
    """
    doc = fitz.open(pdf_path)
    pages = []
    for i, page in enumerate(doc):
        text = extract_page_text(page)
        pages.append({
            "page": i + 1,
            "text": text,
            "char_count": len(text),
        })
    doc.close()
    return pages


def extract_all_pdfs(pdf_dir: str) -> dict:
    """提取目录下所有PDF，返回 {filename: pages_list}"""
    results = {}
    for fname in sorted(os.listdir(pdf_dir)):
        if not fname.endswith(".pdf"):
            continue
        pdf_path = os.path.join(pdf_dir, fname)
        pages = extract_pdf_text(pdf_path)
        total_chars = sum(p["char_count"] for p in pages)
        results[fname] = {
            "pages": pages,
            "total_chars": total_chars,
            "page_count": len(pages),
        }
    return results


if __name__ == "__main__":
    import sys
    pdf_dir = sys.argv[1] if len(sys.argv) > 1 else "assets/references"
    for fname, data in extract_all_pdfs(pdf_dir).items():
        print(f"{fname}: {data['page_count']}页, {data['total_chars']}字")
