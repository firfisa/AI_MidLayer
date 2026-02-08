# 快速入门指南

> 5 分钟上手 AI MidLayer

## 安装

```bash
# 克隆项目
git clone https://github.com/yourusername/ai-midlayer.git
cd ai-midlayer

# 创建虚拟环境 (推荐使用 conda)
conda create -n midlayer python=3.11
conda activate midlayer

# 安装
pip install -e ".[dev]"
```

## 第一步：初始化知识库

```bash
midlayer init
```

这会在当前目录创建 `.midlayer/` 文件夹。

## 第二步：添加文档

```bash
# 添加单个文件
midlayer add README.md

# 添加整个目录
midlayer add docs/

# 添加代码文件
midlayer add src/
```

每个文件会自动：
1. 解析内容
2. 分割成 chunks
3. 创建向量索引 (语义搜索)
4. 创建 BM25 索引 (关键词搜索)

## 第三步：搜索

```bash
# 混合搜索 (推荐)
midlayer search "如何使用装饰器"

# 查看详细信息
midlayer search "error code 401" --verbose

# 仅向量搜索
midlayer search "相似内容" --no-hybrid
```

## 第四步：配置 LLM (可选)

如果要使用问答功能，需要配置 LLM：

```bash
# 使用 DeepSeek (推荐，便宜又好用)
export MIDLAYER_API_KEY="your-deepseek-api-key"
export MIDLAYER_BASE_URL="https://api.deepseek.com/v1"
export MIDLAYER_LLM_MODEL="deepseek-chat"

# 或使用 OpenAI
export MIDLAYER_API_KEY="sk-xxx"
export MIDLAYER_LLM_MODEL="gpt-4o-mini"
```

## 第五步：问答

```bash
# 单次问答
midlayer ask "这个项目的主要功能是什么？"

# 交互式对话
midlayer chat
```

---

## Python SDK 使用

### 基本使用

```python
from ai_midlayer.knowledge.store import FileStore
from ai_midlayer.knowledge.index import VectorIndex
from ai_midlayer.knowledge.bm25 import BM25Index
from ai_midlayer.knowledge.retriever import Retriever

# 初始化
store = FileStore(".midlayer")
vector_index = VectorIndex(".midlayer")
bm25_index = BM25Index(".midlayer/index/bm25.db")

# 添加文档
doc_id = store.add_file("my_document.md")
doc = store.get_file(doc_id)
vector_index.index_document(doc)
bm25_index.index_document(doc)

# 搜索
retriever = Retriever(store, vector_index, bm25_index)
results = retriever.retrieve("搜索内容", top_k=5)

for r in results:
    print(f"[{r.score:.2f}] {r.chunk.content[:100]}")
```

### RAG 问答

```python
from ai_midlayer.llm import LiteLLMClient
from ai_midlayer.rag.query import RAGQueryEngine

# 配置 LLM
llm = LiteLLMClient(
    model="deepseek-chat",
    api_key="your-key",
    base_url="https://api.deepseek.com/v1",
)

# 创建 RAG 引擎
rag = RAGQueryEngine(retriever, llm)

# 问答
answer = rag.query("这个项目解决什么问题？")
print(answer)
```

---

## 使用自定义嵌入模型

默认使用本地模型 `all-MiniLM-L6-v2`，可以切换到 API 模型：

```bash
# 环境变量方式
export MIDLAYER_EMBEDDING_MODEL="text-embedding-3-small"
export MIDLAYER_EMBEDDING_API_KEY="sk-xxx"
export MIDLAYER_EMBEDDING_BASE_URL="https://api.openai.com/v1"
```

或在代码中：

```python
from ai_midlayer.knowledge.index import VectorIndex

index = VectorIndex(
    ".midlayer",
    embedding_model="text-embedding-3-small",
    embedding_api_key="sk-xxx",
    embedding_base_url="https://api.openai.com/v1",
)
```

---

## 下一步

- 查看 [CLI 命令参考](api/cli.md)
- 查看 [Knowledge API](api/knowledge.md)
- 查看 [RAG API](api/rag.md)
- 运行 [Benchmark 测试](../scripts/realistic_benchmark.py)
