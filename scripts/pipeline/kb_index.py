# -*- coding: utf-8 -*-
"""
构建和维护ChromaDB向量索引
用法:
  python -m scripts.pipeline.kb_index --rebuild          # 重建全部索引
  python -m scripts.pipeline.kb_index --collection frameworks  # 只索引指定collection
"""

import os
import sys
import json
import re
import argparse
import chromadb

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
CHROMA_DIR = os.path.join(PROJECT_ROOT, "knowledge/chroma_db")
KB_DIR = os.path.join(PROJECT_ROOT, "knowledge")


def get_client():
    return chromadb.PersistentClient(path=CHROMA_DIR)


def split_by_sentence(text: str) -> list:
    """按中文句末标点切分"""
    parts = re.split(r'([。！？；])', text)
    sentences = []
    for i in range(0, len(parts) - 1, 2):
        sentences.append(parts[i] + parts[i + 1])
    if len(parts) % 2 == 1 and parts[-1]:
        sentences.append(parts[-1])
    return sentences


def chunk_chinese_text(text: str, max_chars: int = 500, overlap: int = 50) -> list:
    """
    按段落边界切分中文文本。
    策略：按双换行分段 → 合并小段直到max_chars → 超长段按句切分 → 添加重叠
    """
    # 先按段落分
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

    chunks = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 <= max_chars:
            current = current + "\n\n" + para if current else para
        else:
            if current:
                chunks.append(current)
            if len(para) > max_chars:
                sentences = split_by_sentence(para)
                sub_chunk = ""
                for s in sentences:
                    if len(sub_chunk) + len(s) <= max_chars:
                        sub_chunk += s
                    else:
                        if sub_chunk:
                            chunks.append(sub_chunk)
                        sub_chunk = s
                current = sub_chunk
            else:
                current = para

    if current:
        chunks.append(current)

    # 添加重叠
    if overlap > 0 and len(chunks) > 1:
        overlapped = [chunks[0]]
        for i in range(1, len(chunks)):
            prev_tail = chunks[i - 1][-overlap:]
            overlapped.append(prev_tail + chunks[i])
        chunks = overlapped

    return chunks


def index_file(collection, file_path: str, metadata: dict):
    """将单个markdown文件索引到ChromaDB collection"""
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()

    # 去掉头部的元信息（---分隔符之前的内容）
    if text.startswith("#"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            text = parts[2].strip()

    chunks = chunk_chinese_text(text, max_chars=500, overlap=50)
    if not chunks:
        return 0

    ids = []
    documents = []
    metadatas = []

    for i, chunk in enumerate(chunks):
        chunk_id = f"{metadata['id']}_chunk_{i:03d}"
        ids.append(chunk_id)
        documents.append(chunk)
        metadatas.append({
            "source": metadata.get("source", ""),
            "title": metadata.get("title", ""),
            "category": metadata.get("category", ""),
            "chunk_index": i,
            "total_chunks": len(chunks),
        })

    collection.add(ids=ids, documents=documents, metadatas=metadatas)
    return len(chunks)


def build_index(rebuild: bool = False, target_collection: str = None):
    """构建或重建ChromaDB索引"""
    client = get_client()

    if rebuild:
        for col in client.list_collections():
            client.delete_collection(col.name)
            print(f"  删除collection: {col.name}")

    # 创建collections
    collections = {}
    for col_name, desc in [
        ("frameworks", "写作框架与方法论"),
        ("materials", "素材与参考资料"),
        ("constraints", "约束规则与标准"),
    ]:
        if target_collection and col_name != target_collection:
            continue
        collections[col_name] = client.get_or_create_collection(
            name=col_name,
            metadata={"description": desc},
        )

    # 读取元数据
    meta_path = os.path.join(KB_DIR, "metadata.json")
    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        entries = metadata.get("entries", [])
    else:
        entries = []
        print("  [WARN] metadata.json不存在，将扫描目录")

    # 索引PDF提取的文件
    total_chunks = 0
    for entry in entries:
        col_name = entry.get("chroma_collection", entry.get("category", ""))
        if target_collection and col_name != target_collection:
            continue
        collection = collections.get(col_name)
        if not collection:
            continue

        file_path = os.path.join(PROJECT_ROOT, entry["output"])
        if os.path.exists(file_path):
            n = index_file(collection, file_path, entry)
            total_chunks += n
            print(f"  索引 {entry['title']}: {n}个块")

    # 索引materials目录下的额外文件
    materials_dir = os.path.join(KB_DIR, "materials")
    if (not target_collection or target_collection == "materials") and "materials" in collections:
        col = collections["materials"]
        for fname in os.listdir(materials_dir):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(materials_dir, fname)
            # 跳过已在metadata中的文件
            if any(e["output"].endswith(fname) for e in entries):
                continue
            meta = {
                "id": f"materials-{fname.replace('.md', '')}",
                "title": fname.replace(".md", ""),
                "source": f"knowledge/materials/{fname}",
                "category": "materials",
            }
            n = index_file(col, fpath, meta)
            total_chunks += n
            print(f"  索引 {fname}: {n}个块")

        # 索引exam-analyses子目录
        exam_dir = os.path.join(materials_dir, "exam-analyses")
        if os.path.exists(exam_dir):
            for fname in os.listdir(exam_dir):
                if not fname.endswith(".md"):
                    continue
                fpath = os.path.join(exam_dir, fname)
                meta = {
                    "id": f"exam-{fname.replace('.md', '')}",
                    "title": fname.replace(".md", ""),
                    "source": f"knowledge/materials/exam-analyses/{fname}",
                    "category": "materials",
                }
                n = index_file(col, fpath, meta)
                total_chunks += n
                print(f"  索引 {fname}: {n}个块")

    # 索引constraints目录
    constraints_dir = os.path.join(KB_DIR, "constraints")
    if (not target_collection or target_collection == "constraints") and "constraints" in collections:
        col = collections["constraints"]
        for fname in os.listdir(constraints_dir):
            if not fname.endswith(".md") or fname == "README.md":
                continue
            fpath = os.path.join(constraints_dir, fname)
            if any(e["output"].endswith(fname) for e in entries):
                continue
            meta = {
                "id": f"constraint-{fname.replace('.md', '')}",
                "title": fname.replace(".md", ""),
                "source": f"knowledge/constraints/{fname}",
                "category": "constraints",
            }
            n = index_file(col, fpath, meta)
            total_chunks += n
            print(f"  索引 {fname}: {n}个块")

    print(f"\n索引构建完成: 共 {total_chunks} 个块")

    # 打印各collection统计
    for col in client.list_collections():
        print(f"  {col.name}: {col.count()} 个块")


def main():
    parser = argparse.ArgumentParser(description="构建ChromaDB向量索引")
    parser.add_argument("--rebuild", action="store_true", help="重建全部索引")
    parser.add_argument("--collection", type=str, help="只索引指定collection")
    args = parser.parse_args()

    build_index(rebuild=args.rebuild, target_collection=args.collection)


if __name__ == "__main__":
    main()
