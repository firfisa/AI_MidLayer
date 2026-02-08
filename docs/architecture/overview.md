# 系统架构

> AI MidLayer 整体架构设计与模块说明

## 架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                        L4: Interface Layer                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   CLI       │  │   Python    │  │   REST API (future)     │  │
│  │  midlayer   │  │     SDK     │  │                         │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                     L3: RAG & Orchestration                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ RAGQuery    │  │ Reranker    │  │   Query Expansion       │  │
│  │  Engine     │  │  (LLM)      │  │   (HyDE)                │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│  ┌─────────────┐  ┌─────────────┐                               │
│  │ Fusion      │  │ Orchestrator│                               │
│  │  (RRF)      │  │  (Pipeline) │                               │
│  └─────────────┘  └─────────────┘                               │
├─────────────────────────────────────────────────────────────────┤
│                      L2: Knowledge Layer                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ FileStore   │  │ VectorIndex │  │   BM25Index             │  │
│  │  (解析)     │  │  (LanceDB)  │  │   (SQLite FTS5)         │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ Retriever   │  │ Embedding   │  │   Document/Chunk        │  │
│  │  (混合检索) │  │  Client     │  │   Models                │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                       L1: Agent Layer                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ OODA Loop   │  │ Reflexion   │  │   LLM Agent Mixin       │  │
│  │  (循环)     │  │  (自省)     │  │                         │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│  ┌─────────────┐  ┌─────────────┐                               │
│  │ ParserAgent │  │ Structure   │                               │
│  │             │  │   Agent     │                               │
│  └─────────────┘  └─────────────┘                               │
├─────────────────────────────────────────────────────────────────┤
│                        L0: LLM Layer                             │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │   LiteLLMClient (OpenAI, DeepSeek, Claude, Gemini, ...)    ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

---

## 分层设计

### L0: LLM Layer

底层大语言模型适配。

| 组件 | 文件 | 功能 |
|------|------|------|
| LiteLLMClient | `llm/__init__.py` | 统一 LLM 接口 |

**特点:**
- 支持多种 LLM 提供商
- 统一的 API 调用接口
- 可配置的 base_url 和 api_key

### L1: Agent Layer

智能 Agent 能力。

| 组件 | 文件 | 功能 |
|------|------|------|
| OODAAgent | `agents/base.py` | OODA 循环基类 |
| ReflexionMixin | `agents/reflexion.py` | 自省增强 |
| LLMAgentMixin | `agents/llm_agent.py` | LLM 决策能力 |
| ParserAgent | `agents/parser.py` | 文档解析 |
| StructureAgent | `agents/structure.py` | 结构识别 |

**OODA 循环:**
```
Observe → Orient → Decide → Act → (loop)
```

### L2: Knowledge Layer

知识管理核心。

| 组件 | 文件 | 功能 |
|------|------|------|
| FileStore | `knowledge/store.py` | 文档存储 |
| VectorIndex | `knowledge/index.py` | 向量索引 (LanceDB) |
| BM25Index | `knowledge/bm25.py` | 关键词索引 (SQLite FTS5) |
| Retriever | `knowledge/retriever.py` | 混合检索 |
| EmbeddingClient | `knowledge/embedding.py` | 嵌入生成 |

**数据流:**
```
File → FileStore → Document → Chunking → VectorIndex + BM25Index
                                              ↓
Query → Retriever ← [Vector Results + BM25 Results] → RRF Fusion
```

### L3: RAG & Orchestration

检索增强生成。

| 组件 | 文件 | 功能 |
|------|------|------|
| RAGQueryEngine | `rag/query.py` | RAG 查询 |
| Fusion | `rag/fusion.py` | RRF 结果融合 |
| LLMReranker | `rag/reranker.py` | LLM 重排序 |
| QueryExpander | `rag/expansion.py` | 查询扩展 + HyDE |
| Orchestrator | `orchestrator/` | 流程编排 |

**RAG 流程:**
```
Query → [Expansion] → Retrieval → [Rerank] → Context → LLM → Answer
```

### L4: Interface Layer

用户接口。

| 组件 | 文件 | 功能 |
|------|------|------|
| CLI | `cli/main.py` | 命令行工具 |
| Python SDK | `*` | 代码调用 |

---

## 核心设计决策

### 1. 混合搜索 (Hybrid Search)

结合关键词精确匹配和语义相似度：

```
┌─────────────┐              ┌─────────────┐
│   BM25      │              │   Vector    │
│  (精确匹配) │              │  (语义相似) │
└──────┬──────┘              └──────┬──────┘
       │                            │
       └────────┬───────────────────┘
                │
         ┌──────▼──────┐
         │  RRF Fusion │
         │  (2:1 权重) │
         └──────┬──────┘
                │
         ┌──────▼──────┐
         │   Results   │
         └─────────────┘
```

**优势:**
- BM25 对函数名、错误码等精确匹配优秀
- Vector 对语义理解、同义词匹配优秀
- RRF 融合取两者之长

### 2. 嵌入模型支持

```
┌─────────────────────────────────────────┐
│           EmbeddingClient               │
├─────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────────┐  │
│  │ Local Model │  │ API Model       │  │
│  │ (MiniLM)    │  │ (OpenAI, etc)   │  │
│  └─────────────┘  └─────────────────┘  │
└─────────────────────────────────────────┘
```

**支持模型:**
- 本地: `all-MiniLM-L6-v2`
- API: `text-embedding-3-small/large`
- 自定义: 任何 OpenAI 兼容 API

### 3. 分块策略

```
Document (N chars)
    ↓
┌─────────────────────────────────────────┐
│  Chunk 1 (500 chars)                    │
│                          ────────────┐  │
└──────────────────────────            │  │
                           ┌───────────┴──┤
                           │  Chunk 2     │
                           │   (500)      │
                           │       ────┐  │
                           └───────────┴──┤
                                    ┌─────┴─────┐
                                    │  Chunk 3  │
                                    └───────────┘
```

**参数:**
- Chunk Size: 500 字符
- Overlap: 100 字符
- 智能断句 (句号、换行)

---

## 目录结构

```
ai-midlayer/
├── src/ai_midlayer/           # 源代码
│   ├── __init__.py
│   ├── config.py             # 配置管理
│   │
│   ├── llm/                  # L0: LLM Layer
│   │   └── __init__.py
│   │
│   ├── agents/               # L1: Agent Layer
│   │   ├── base.py          # OODA 基类
│   │   ├── reflexion.py     # Reflexion
│   │   ├── llm_agent.py     # LLM Mixin
│   │   ├── parser.py        # 解析 Agent
│   │   └── structure.py     # 结构 Agent
│   │
│   ├── knowledge/            # L2: Knowledge Layer
│   │   ├── models.py        # 数据模型
│   │   ├── store.py         # 文档存储
│   │   ├── index.py         # 向量索引
│   │   ├── bm25.py          # BM25 索引
│   │   ├── embedding.py     # 嵌入客户端
│   │   ├── retriever.py     # 检索器
│   │   └── hybrid.py        # 混合检索器
│   │
│   ├── rag/                  # L3: RAG Layer
│   │   ├── query.py         # 查询引擎
│   │   ├── fusion.py        # 结果融合
│   │   ├── reranker.py      # 重排序
│   │   └── expansion.py     # 查询扩展
│   │
│   ├── orchestrator/         # L3: Orchestration
│   │   └── __init__.py
│   │
│   └── cli/                  # L4: Interface
│       └── main.py
│
├── tests/                    # 测试
├── docs/                     # 文档
├── scripts/                  # 工具脚本
└── memory-bank/              # 项目记忆
```

---

## 数据存储

### 知识库目录结构

```
.midlayer/
├── store/                    # 文档存储
│   ├── raw/                 # 原始文件备份
│   ├── parsed/              # 解析后的 JSON
│   └── index.json           # 文件索引
│
├── index/                    # 索引
│   ├── vector_store/        # LanceDB 向量数据
│   │   └── chunks.lance/
│   └── bm25.db              # SQLite FTS5 数据库
│
└── config.json               # 配置 (future)
```

---

## 技术栈

| 类别 | 技术 |
|------|------|
| 语言 | Python 3.11+ |
| 向量数据库 | LanceDB |
| 全文搜索 | SQLite FTS5 |
| 嵌入 | sentence-transformers / OpenAI API |
| LLM | LiteLLM (多模型支持) |
| CLI | Typer + Rich |
| 配置 | Pydantic |
| 测试 | pytest |
