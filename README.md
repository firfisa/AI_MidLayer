# AI MidLayer

<div align="center">

**🧠 大模型上下文中间层 - 将杂乱的项目资料转化为高质量 LLM 上下文**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-82%20passed-green.svg)]()
[![License](https://img.shields.io/badge/license-MIT-lightgrey.svg)]()

[快速开始](#-快速开始) •
[核心功能](#-核心功能) •
[架构设计](#-架构设计) •
[API 文档](#-api-参考) •
[配置指南](#-配置)

</div>

---

## 🎯 项目愿景

AI MidLayer 是一个**智能上下文管理系统**，旨在解决大模型使用中的核心痛点：

| 痛点 | 解决方案 |
|------|----------|
| 📄 信息碎片化 | 统一的知识库管理，自动解析多种文件格式 |
| 🔍 检索不精准 | 混合搜索 (BM25 + Vector + RRF 融合) |
| 🤖 上下文质量差 | LLM 重排序 + HyDE 查询扩展 |
| 💬 交互体验差 | 交互式 RAG 对话，带记忆的多轮对话 |

## 🚀 快速开始

### 安装

```bash
# 克隆项目
git clone https://github.com/yourusername/ai-midlayer.git
cd ai-midlayer

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装
pip install -e ".[dev]"
```

### 基本使用

```bash
# 1. 初始化知识库
midlayer init

# 2. 添加文档 (自动双索引: Vector + BM25)
midlayer add docs/
midlayer add README.md

# 3. 语义搜索 (混合搜索默认开启)
midlayer search "如何配置嵌入模型"

# 4. 单次问答
midlayer ask "这个项目的主要功能是什么？"

# 5. 交互式对话 (支持历史记忆)
midlayer chat
```

### 配置 LLM

```bash
# 使用 OpenAI
export MIDLAYER_API_KEY="sk-xxx"
export MIDLAYER_LLM_MODEL="gpt-4o-mini"

# 使用 DeepSeek
export MIDLAYER_API_KEY="sk-xxx"
export MIDLAYER_BASE_URL="https://api.deepseek.com/v1"
export MIDLAYER_LLM_MODEL="deepseek-chat"

# 使用自定义端点
export MIDLAYER_BASE_URL="https://your-api.com/v1"
```

## ✨ 核心功能

### 1. 智能文档解析

```python
from ai_midlayer.knowledge.store import FileStore

store = FileStore(".midlayer")
doc_id = store.add_file("paper.pdf")  # 支持 PDF, MD, TXT, 代码文件
doc = store.get_file(doc_id)
print(doc.content)  # 自动解析内容
```

### 2. 混合搜索 (Hybrid Search)

结合 BM25 精确匹配和向量语义搜索，使用 RRF 融合算法：

```python
from ai_midlayer.knowledge.retriever import Retriever
from ai_midlayer.knowledge.store import FileStore
from ai_midlayer.knowledge.index import VectorIndex
from ai_midlayer.knowledge.bm25 import BM25Index

# 初始化组件
store = FileStore(".midlayer")
vector_index = VectorIndex(".midlayer")
bm25_index = BM25Index(".midlayer/index/bm25.db")

# 创建混合检索器
retriever = Retriever(store, vector_index, bm25_index)

# 搜索
results = retriever.retrieve("Python 装饰器", top_k=5)
for r in results:
    print(f"[{r.score:.2f}] {r.chunk.content[:100]}")
```

### 3. RAG 问答

```python
from ai_midlayer.rag.query import RAGQueryEngine
from ai_midlayer.llm import LiteLLMClient

# 创建 RAG 引擎
llm = LiteLLMClient(model="gpt-4o-mini")
rag = RAGQueryEngine(retriever, llm)

# 单次问答
answer = rag.query("这个项目解决什么问题？")
print(answer)

# 多轮对话 (带记忆)
session = rag.create_session()
answer1 = session.chat("项目架构是什么？")
answer2 = session.chat("详细说说检索模块")  # 记住上下文
```

### 4. 自定义嵌入模型

支持本地模型和 OpenAI 兼容 API：

```python
from ai_midlayer.knowledge.index import VectorIndex

# 使用 OpenAI 嵌入
index = VectorIndex(
    ".midlayer",
    embedding_model="text-embedding-3-small",
    embedding_api_key="sk-xxx",
    embedding_base_url="https://api.openai.com/v1",
    embedding_dimensions=1536,
)

# 或使用本地模型 (需安装 sentence-transformers)
index = VectorIndex(".midlayer")  # 默认使用 all-MiniLM-L6-v2
```

## 🏗 架构设计

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
├─────────────────────────────────────────────────────────────────┤
│                      L2: Knowledge Layer                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ FileStore   │  │ VectorIndex │  │   BM25Index             │  │
│  │  (解析)     │  │  (LanceDB)  │  │   (SQLite FTS5)         │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ Retriever   │  │ Embedding   │  │   Fusion (RRF)          │  │
│  │  (混合检索) │  │  Client     │  │                         │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                       L1: Agent Layer                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ OODA Loop   │  │ Reflexion   │  │   LLM Agent Mixin       │  │
│  │  (循环)     │  │  (自省)     │  │                         │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                        L0: LLM Layer                             │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │   LiteLLMClient (OpenAI, DeepSeek, Claude, Gemini, ...)    ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

### 模块说明

| 模块 | 路径 | 功能 |
|------|------|------|
| **knowledge** | `src/ai_midlayer/knowledge/` | 文档存储、向量索引、BM25索引、检索器、嵌入 |
| **rag** | `src/ai_midlayer/rag/` | RAG查询、重排序、查询扩展、结果融合 |
| **agents** | `src/ai_midlayer/agents/` | OODA循环、Reflexion、结构识别 |
| **llm** | `src/ai_midlayer/llm/` | LLM适配器 (LiteLLM) |
| **cli** | `src/ai_midlayer/cli/` | 命令行接口 |
| **config** | `src/ai_midlayer/config.py` | 配置管理 |

## 📖 API 参考

### FileStore - 文档存储

```python
from ai_midlayer.knowledge.store import FileStore

store = FileStore(kb_path=".midlayer")

# 添加文件
doc_id = store.add_file("doc.md")

# 获取文档
doc = store.get_file(doc_id)

# 列出所有文档
docs = store.list_files()

# 删除文档
store.remove_file(doc_id)
```

### VectorIndex - 向量索引

```python
from ai_midlayer.knowledge.index import VectorIndex

index = VectorIndex(
    kb_path=".midlayer",
    embedding_model="text-embedding-3-small",  # 可选
    embedding_api_key="sk-xxx",                 # 可选
    embedding_base_url="https://api.openai.com/v1",  # 可选
)

# 索引文档
num_chunks = index.index_document(doc)

# 搜索
results = index.search("query", top_k=5)

# 统计
stats = index.get_stats()
# {"total_chunks": 100, "total_documents": 10, "embedding_model": "...", "use_api": True}
```

### BM25Index - 关键词索引

```python
from ai_midlayer.knowledge.bm25 import BM25Index

bm25 = BM25Index(db_path=".midlayer/index/bm25.db")

# 索引文档
num_chunks = bm25.index_document(doc)

# 搜索 (精确关键词匹配)
results = bm25.search("error code 401", top_k=5)
```

### Retriever - 混合检索

```python
from ai_midlayer.knowledge.retriever import Retriever

retriever = Retriever(
    store=store,
    index=vector_index,
    bm25_index=bm25_index,  # 可选，启用混合搜索
)

# 检查混合搜索状态
print(retriever.hybrid_enabled)  # True

# 检索 (自动使用混合搜索)
results = retriever.retrieve("query", top_k=5)

# 强制只用向量搜索
results = retriever.retrieve("query", top_k=5, use_hybrid=False)
```

### EmbeddingClient - 嵌入客户端

```python
from ai_midlayer.knowledge.embedding import EmbeddingClient

# API 模式
client = EmbeddingClient(
    model="text-embedding-3-small",
    api_key="sk-xxx",
    base_url="https://api.openai.com/v1",
    dimensions=1536,
)

# 本地模式
client = EmbeddingClient(model="all-MiniLM-L6-v2")

# 生成嵌入
embeddings = client.embed(["text1", "text2"])
embedding = client.embed_single("single text")
```

### RAGQueryEngine - RAG 问答

```python
from ai_midlayer.rag.query import RAGQueryEngine

rag = RAGQueryEngine(retriever, llm)

# 单次问答
answer = rag.query("问题")

# 多轮对话
session = rag.create_session()
answer = session.chat("问题1")
answer = session.chat("追问")  # 记住上下文
```

## ⚙️ 配置

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `MIDLAYER_API_KEY` | LLM API Key | - |
| `MIDLAYER_BASE_URL` | LLM API Base URL | - |
| `MIDLAYER_LLM_MODEL` | LLM 模型名 | `gpt-4o-mini` |
| `MIDLAYER_LLM_PROVIDER` | 提供商 | `openai` |
| `MIDLAYER_EMBEDDING_MODEL` | 嵌入模型 | `all-MiniLM-L6-v2` |
| `MIDLAYER_EMBEDDING_API_KEY` | 嵌入 API Key | - |
| `MIDLAYER_EMBEDDING_BASE_URL` | 嵌入 API URL | - |
| `MIDLAYER_EMBEDDING_DIMENSIONS` | 嵌入维度 | `1536` |
| `MIDLAYER_KB_PATH` | 知识库路径 | `.midlayer` |

### 配置示例

```bash
# ~/.zshrc 或 ~/.bashrc

# DeepSeek (推荐，性价比高)
export MIDLAYER_API_KEY="sk-xxx"
export MIDLAYER_BASE_URL="https://api.deepseek.com/v1"
export MIDLAYER_LLM_MODEL="deepseek-chat"

# 自定义嵌入 (可选)
export MIDLAYER_EMBEDDING_MODEL="text-embedding-3-small"
export MIDLAYER_EMBEDDING_API_KEY="sk-xxx"
export MIDLAYER_EMBEDDING_BASE_URL="https://api.openai.com/v1"
```

## 🧪 测试

```bash
# 运行所有测试
pytest

# 运行特定模块测试
pytest tests/test_knowledge.py -v

# 运行 Benchmark
python scripts/realistic_benchmark.py
python scripts/compare_embeddings.py
python scripts/dogfood_test.py
```

### 测试覆盖

| 模块 | 测试数 |
|------|--------|
| agents | 10 |
| hybrid | 13 |
| hybrid_e2e | 7 |
| index | 8 |
| knowledge | 6 |
| llm | 15 |
| rag | 9 |
| reranker | 16 |
| **总计** | **82** |

## 📁 项目结构

```
ai-midlayer/
├── src/ai_midlayer/           # 源代码
│   ├── agents/                # Agent 模块
│   │   ├── base.py           # OODA 基类
│   │   ├── reflexion.py      # Reflexion 增强
│   │   ├── llm_agent.py      # LLM Agent Mixin
│   │   └── structure.py      # 结构识别 Agent
│   ├── cli/                   # CLI 模块
│   │   └── main.py           # 命令行入口
│   ├── knowledge/             # 知识管理模块
│   │   ├── store.py          # 文档存储
│   │   ├── index.py          # 向量索引
│   │   ├── bm25.py           # BM25 索引
│   │   ├── embedding.py      # 嵌入客户端
│   │   ├── retriever.py      # 检索器
│   │   ├── hybrid.py         # 混合检索器
│   │   └── models.py         # 数据模型
│   ├── llm/                   # LLM 模块
│   │   └── __init__.py       # LiteLLM 适配器
│   ├── rag/                   # RAG 模块
│   │   ├── query.py          # 查询引擎
│   │   ├── fusion.py         # 结果融合
│   │   ├── reranker.py       # 重排序
│   │   └── expansion.py      # 查询扩展
│   └── config.py             # 配置管理
├── tests/                     # 测试
├── scripts/                   # 工具脚本
│   ├── dogfood_test.py       # 自测脚本
│   ├── realistic_benchmark.py # 真实场景 Benchmark
│   └── compare_embeddings.py  # 嵌入模型对比
├── docs/                      # 文档
├── memory-bank/               # 项目记忆 (Vibe Coding)
└── pyproject.toml            # 项目配置
```

## 🛣 路线图

### ✅ 已完成

- [x] Phase 1: 核心管线 (解析、索引、检索)
- [x] Phase 2: Agentic 增强 (OODA、Reflexion)
- [x] Phase 3: RAG 用户体验 (chat、ask)
- [x] Phase 4: QMD 混合搜索 (BM25、RRF、重排序、HyDE)
- [x] 自定义嵌入模型支持

### 🚧 进行中

- [ ] 配置文件支持 (.midlayer.yaml)
- [ ] REST API 接口

### 📋 计划中

- [ ] Web UI
- [ ] 模型微调接口
- [ ] 多模态支持 (图片、音视频)
- [ ] 知识图谱集成

## 🤝 贡献

欢迎贡献！请查看 [CONTRIBUTING.md](docs/CONTRIBUTING.md) 了解详情。

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE)

---

<div align="center">
Made with ❤️ for better AI interactions
</div>
