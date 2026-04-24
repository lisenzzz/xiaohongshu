# -*- coding: utf-8 -*-
"""MiMo LLM文本纠错模块"""

import sys
import os
import time
import requests

# 添加项目根目录到path以导入config
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from scripts.config import MIMO_API_URL, MIMO_API_KEY, MIMO_MODEL

CORRECT_SYSTEM_PROMPT = """你是一个中文文本校对专家。你的任务是修正从PDF中提取的文本，修复以下问题：
1. OCR识别错误（错别字、乱码）
2. 断行不当导致的句子断裂
3. 标点符号错误
4. 格式混乱（多余的空行、缩进不一致）

规则：
- 保持原文意思不变，不要添加或删减内容
- 保持原文的段落结构
- 修复明显的错别字和语病
- 对于不确定的内容，保持原文不动
- 输出纯文本，不要加markdown格式标记"""


def call_mimo_correct(text: str) -> str:
    """单次MiMo API调用进行文本纠错"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {MIMO_API_KEY}",
    }
    payload = {
        "model": MIMO_MODEL,
        "messages": [
            {"role": "system", "content": CORRECT_SYSTEM_PROMPT},
            {"role": "user", "content": f"请校对以下文本：\n\n{text}"},
        ],
        "temperature": 0.3,
        "max_tokens": 4000,
    }
    resp = requests.post(MIMO_API_URL, json=payload, headers=headers, timeout=120)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def chunk_text(text: str, max_chars: int = 2500) -> list:
    """按段落边界切分文本，每块不超过max_chars"""
    paragraphs = text.split("\n")
    chunks = []
    current = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            if current:
                current += "\n"
            continue

        if len(current) + len(para) + 1 <= max_chars:
            current = current + "\n" + para if current else para
        else:
            if current:
                chunks.append(current)
            if len(para) > max_chars:
                # 按句号切分超长段落
                import re
                parts = re.split(r'([。！？])', para)
                sub_chunk = ""
                for j in range(0, len(parts) - 1, 2):
                    sentence = parts[j] + parts[j + 1]
                    if len(sub_chunk) + len(sentence) <= max_chars:
                        sub_chunk += sentence
                    else:
                        if sub_chunk:
                            chunks.append(sub_chunk)
                        sub_chunk = sentence
                if len(parts) % 2 == 1 and parts[-1]:
                    sub_chunk += parts[-1]
                current = sub_chunk
            else:
                current = para

    if current:
        chunks.append(current)
    return chunks


def correct_text_batch(text_chunks: list, delay: float = 1.5) -> list:
    """批量纠错，带速率限制"""
    results = []
    total = len(text_chunks)
    for i, chunk in enumerate(text_chunks):
        try:
            corrected = call_mimo_correct(chunk)
            results.append(corrected)
            print(f"  纠错进度: {i + 1}/{total} ({len(chunk)}字 -> {len(corrected)}字)")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                print(f"  速率限制，等待10秒后重试...")
                time.sleep(10)
                corrected = call_mimo_correct(chunk)
                results.append(corrected)
            else:
                print(f"  API错误: {e}，保留原文")
                results.append(chunk)
        if i < total - 1:
            time.sleep(delay)
    return results
