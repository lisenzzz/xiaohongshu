# 小红书内容工作空间 - Agent 指南

## 身份

本工作空间服务于"上海思辨写作云老师"小红书账号（8年高三 · 四校私教）。
核心方法论：破题三步法 + 一类文八段式 + 二元对立思辨框架。

## 目录导航

| 目录 | 用途 | 何时使用 |
|------|------|----------|
| `knowledge/frameworks/` | 21讲PDF提取的写作方法论 | 需要框架/技巧时 |
| `knowledge/materials/` | 素材、范文、考试分析 | 需要论据/案例时 |
| `knowledge/constraints/` | 风格约束、评分标准、素材库 | **每次创作必读** |
| `knowledge/chroma_db/` | 向量数据库 | 语义搜索时 |
| `posts/ideas/` | 选题报告与灵感 | 选题阶段 |
| `posts/drafts/` | 草稿 | 创作阶段 |
| `posts/published/` | 已发布帖子 | 归档 |
| `memory/` | 经验沉淀 | **每次创作必读** |
| `scripts/pipeline/` | PDF处理与知识检索工具 | 知识库维护 |
| `scripts/xhs_*.py` | 小红书爬虫与选题 | 数据收集 |
| `templates/` | 帖子模板 | 创作阶段 |

## 每次创作前必读

1. `knowledge/constraints/content-preferences.md` - 身份 · 风格 · 格式硬约束
2. `memory/v1-feedback.md` - 历史审稿反馈
3. `memory/content-creation-lessons.md` - 创作经验

## 素材使用原则

- **必须从 `knowledge/` 中提取**，不要编造素材
- 优先使用课内素材（苏轼、庄子、鲁迅等）
- 课外理论每个只用一句话 + 紧跟分析
- 黑名单素材（司马迁、爱迪生等）除非神级新角度否则不用
- 素材出处参考：专题7（社会学理论）、专题17（刘擎西方思想）、专题19（课本素材）、专题21（理论论据）

## 格式硬约束

- 禁用双引号（用书名号替代）
- 禁用破折号（用逗号/句号/自然衔接）
- 禁用排比堆砌（三个及以上并列）
- 禁用否定句式描写
- 用纯数字编号（1. 2. 3.），不用数字emoji
- 帖子标题与封面标题不能一模一样
- 不放任何推销内容

## 调用工具

```bash
# 知识搜索
python -m scripts.pipeline.kb_search "辩证分析" --top_k 5

# 选题搜索
python scripts/xhs_search_topics.py --sort hot

# 帖子分析
python scripts/xhs_scraper.py --account own

# PDF重新处理
python -m scripts.pipeline.pdf_pipeline --pdf 01

# 重建向量索引
python -m scripts.pipeline.kb_index --rebuild
```

## 账号信息

- 昵称：上海思辨写作云老师
- 主页：https://www.xiaohongshu.com/user/profile/5b6f9a34e24fb70001888f8b
- 定位：高中语文写作教学，聚焦上海高考作文
- 受众：高中生（尤其高三）、家长

## Python 环境

```bash
source .venv/bin/activate
python --version  # 3.9.6
pip list          # requests, playwright, pymupdf, chromadb
```
