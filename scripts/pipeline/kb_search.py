# -*- coding: utf-8 -*-
"""
语义搜索知识库
用法:
  python -m scripts.pipeline.kb_search "辩证分析" --top_k 5
  python -m scripts.pipeline.kb_search "苏轼素材" --collection materials
"""

import os
import sys
import argparse
import chromadb

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
CHROMA_DIR = os.path.join(PROJECT_ROOT, "knowledge/chroma_db")


def search(query: str, collection_name: str = None, top_k: int = 5):
    """搜索知识库，返回 [{text, source, title, distance, collection}]"""
    if not os.path.exists(CHROMA_DIR):
        print("错误: 向量数据库不存在，请先运行: python -m scripts.pipeline.kb_index")
        return []

    client = chromadb.PersistentClient(path=CHROMA_DIR)

    if collection_name:
        try:
            cols = [client.get_collection(collection_name)]
        except Exception:
            print(f"错误: collection '{collection_name}' 不存在")
            return []
    else:
        cols = client.list_collections()

    all_results = []
    for col in cols:
        try:
            res = col.query(query_texts=[query], n_results=min(top_k, col.count()))
        except Exception:
            continue
        if not res["documents"] or not res["documents"][0]:
            continue
        for i, doc in enumerate(res["documents"][0]):
            meta = res["metadatas"][0][i] if res["metadatas"] else {}
            all_results.append({
                "text": doc,
                "source": meta.get("source", ""),
                "title": meta.get("title", ""),
                "distance": res["distances"][0][i] if res["distances"] else None,
                "collection": col.name,
            })

    all_results.sort(key=lambda x: x["distance"] or 999)
    return all_results[:top_k]


def format_results(results: list, query: str):
    """格式化输出搜索结果"""
    if not results:
        print(f"未找到与 '{query}' 相关的内容")
        return

    print(f"搜索: {query}")
    print(f"找到 {len(results)} 个结果:\n")
    print("=" * 60)

    for i, r in enumerate(results, 1):
        print(f"\n[{i}] 来源: {r['title']} ({r['collection']})")
        print(f"    文件: {r['source']}")
        if r["distance"] is not None:
            print(f"    距离: {r['distance']:.4f}")
        print(f"    内容: {r['text'][:200]}...")
        print("-" * 60)


def main():
    parser = argparse.ArgumentParser(description="语义搜索知识库")
    parser.add_argument("query", type=str, help="搜索内容")
    parser.add_argument("--top_k", type=int, default=5, help="返回结果数")
    parser.add_argument("--collection", type=str, help="指定collection搜索")
    parser.add_argument("--json", action="store_true", help="JSON格式输出")
    args = parser.parse_args()

    results = search(args.query, collection_name=args.collection, top_k=args.top_k)

    if args.json:
        import json
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        format_results(results, args.query)


if __name__ == "__main__":
    main()
