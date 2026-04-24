# 知识库

本目录是"上海思辨写作云老师"的统一知识库，所有教学内容、素材、约束规则均存储于此。

## 目录结构

| 子目录 | 内容 | 来源 |
|--------|------|------|
| `frameworks/` | 21讲PDF提取的写作方法论 | `assets/references/*.pdf` |
| `materials/` | 素材、范文、考试分析 | 散落的txt文件、deepseek.md |
| `constraints/` | 风格约束、评分标准、素材库 | 原顶层 `constraints/` |
| `chroma_db/` | ChromaDB向量索引（自动生成） | 构建脚本生成 |

## 使用方式

### 语义搜索
```bash
python -m scripts.pipeline.kb_search "辩证分析" --top_k 5
```

### 重建索引
```bash
python -m scripts.pipeline.kb_index --rebuild
```

### PDF重新处理
```bash
python -m scripts.pipeline.pdf_pipeline --pdf 01
```
