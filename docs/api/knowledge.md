# Knowledge 模块 API

> 文档存储、索引和检索的核心模块

## 概览

Knowledge 模块负责：
- 文档解析与存储 (`FileStore`)
- 向量索引与语义搜索 (`VectorIndex`)
- BM25 关键词索引 (`BM25Index`)
- 混合检索 (`Retriever`)
- 嵌入向量生成 (`EmbeddingClient`)

---

## FileStore

文档存储管理，支持多种文件格式的解析和存储。

### 初始化

```python
from ai_midlayer.knowledge.store import FileStore

store = FileStore(kb_path=".midlayer")
```

**参数:**
| 参数 | 类型 | 说明 |
|------|------|------|
| `kb_path` | `str \| Path` | 知识库根目录路径 |

### 方法

#### add_file

添加文件到知识库。

```python
doc_id = store.add_file("path/to/file.md")
```

**参数:**
- `path`: 文件路径

**返回:** 文档 ID (str)

**支持格式:**
- Markdown (`.md`)
- 文本 (`.txt`)
- PDF (`.pdf`) - 需要 pypdf
- Python (`.py`)
- 其他代码文件

#### get_file

获取文档内容。

```python
doc = store.get_file(doc_id)
print(doc.content)
print(doc.file_name)
print(doc.file_type)
```

**返回:** `Document` 对象或 `None`

#### list_files

列出所有文档。

```python
docs = store.list_files()
for doc in docs:
    print(f"{doc.id}: {doc.file_name}")
```

**返回:** `list[Document]`

#### remove_file

删除文档。

```python
store.remove_file(doc_id)
```

---

## VectorIndex

使用 LanceDB 的向量索引，支持自定义嵌入模型。

### 初始化

```python
from ai_midlayer.knowledge.index import VectorIndex

# 本地模型 (默认)
index = VectorIndex(kb_path=".midlayer")

# API 模型
index = VectorIndex(
    kb_path=".midlayer",
    embedding_model="text-embedding-3-small",
    embedding_api_key="sk-xxx",
    embedding_base_url="https://api.openai.com/v1",
    embedding_dimensions=1536,
)
```

**参数:**
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `kb_path` | `str \| Path` | - | 知识库路径 |
| `embedding_model` | `str` | `all-MiniLM-L6-v2` | 嵌入模型名 |
| `embedding_api_key` | `str \| None` | `None` | API Key |
| `embedding_base_url` | `str \| None` | `None` | API Base URL |
| `embedding_dimensions` | `int` | `1536` | 嵌入维度 |

### 方法

#### index_document

索引一个文档。

```python
num_chunks = index.index_document(doc)
print(f"Indexed {num_chunks} chunks")
```

**内部流程:**
1. 将文档分割成重叠的 chunks (500 字符，100 重叠)
2. 生成每个 chunk 的嵌入向量
3. 存储到 LanceDB

#### search

语义相似度搜索。

```python
results = index.search(
    query="Python 装饰器",
    top_k=5,
    filter_doc_id=None,  # 可选：限制搜索范围
)

for r in results:
    print(f"Score: {r.score:.3f}")
    print(f"Content: {r.chunk.content[:100]}")
    print(f"File: {r.chunk.metadata['file_name']}")
```

**返回:** `list[SearchResult]`

#### get_stats

获取索引统计信息。

```python
stats = index.get_stats()
# {
#     "total_chunks": 150,
#     "total_documents": 12,
#     "embedding_model": "text-embedding-3-small",
#     "use_api": True,
# }
```

#### remove_document

删除文档的所有 chunks。

```python
removed = index.remove_document(doc_id)
print(f"Removed {removed} chunks")
```

---

## BM25Index

使用 SQLite FTS5 的 BM25 关键词索引。

### 初始化

```python
from ai_midlayer.knowledge.bm25 import BM25Index

bm25 = BM25Index(db_path=".midlayer/index/bm25.db")
```

### 方法

#### index_document

```python
num_chunks = bm25.index_document(doc)
```

#### search

精确关键词匹配搜索。

```python
results = bm25.search("error 401 unauthorized", top_k=5)
```

**特点:**
- 精确匹配函数名、错误码等
- 支持中文分词
- BM25 相关性评分

---

## Retriever

统一检索接口，支持混合搜索。

### 初始化

```python
from ai_midlayer.knowledge.retriever import Retriever

# 仅向量搜索
retriever = Retriever(store, vector_index)

# 混合搜索 (推荐)
retriever = Retriever(store, vector_index, bm25_index)
```

### 属性

#### hybrid_enabled

```python
if retriever.hybrid_enabled:
    print("混合搜索已启用")
```

### 方法

#### retrieve

主检索方法。

```python
results = retriever.retrieve(
    query="Python 装饰器使用方法",
    top_k=5,
    include_context=True,  # 包含上下文
    use_hybrid=None,  # None=自动, True=强制混合, False=仅向量
)
```

**混合搜索流程:**
1. 同时执行 BM25 和 Vector 搜索
2. 检测 BM25 强信号 (精确匹配)
3. 使用 RRF 融合结果 (BM25 权重 2:1)
4. 返回排序后的结果

**SearchResult 结构:**

```python
class SearchResult:
    chunk: Chunk        # 内容片段
    score: float        # 相关性得分
    
class Chunk:
    id: str
    doc_id: str
    content: str
    start_idx: int
    end_idx: int
    metadata: dict      # file_name, file_type, search_source, rrf_score
```

---

## EmbeddingClient

嵌入向量生成客户端。

### 初始化

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
client = EmbeddingClient()  # 默认 all-MiniLM-L6-v2
```

### 属性

```python
client.model        # 模型名
client.use_api      # 是否使用 API
client.dimensions   # 嵌入维度
```

### 方法

#### embed

批量生成嵌入。

```python
embeddings = client.embed(["text1", "text2", "text3"])
# 返回: list[list[float]]
```

#### embed_single

单个文本嵌入。

```python
embedding = client.embed_single("Hello world")
# 返回: list[float]
```

---

## 数据模型

### Document

```python
from ai_midlayer.knowledge.models import Document

doc = Document(
    id="uuid",
    file_name="example.md",
    file_type="markdown",
    content="...",
    source_path="/path/to/file",
    created_at=datetime.now(),
    chunks=[...],
    metadata={},
)
```

### Chunk

```python
from ai_midlayer.knowledge.models import Chunk

chunk = Chunk(
    id="uuid",
    doc_id="parent_doc_id",
    content="chunk text...",
    start_idx=0,
    end_idx=500,
    metadata={"file_name": "...", "search_source": "hybrid"},
)
```

### SearchResult

```python
from ai_midlayer.knowledge.models import SearchResult

result = SearchResult(
    chunk=chunk,
    score=0.95,
)
```

---

## 使用示例

### 完整的索引和搜索流程

```python
from ai_midlayer.knowledge.store import FileStore
from ai_midlayer.knowledge.index import VectorIndex
from ai_midlayer.knowledge.bm25 import BM25Index
from ai_midlayer.knowledge.retriever import Retriever

# 1. 初始化组件
kb_path = ".midlayer"
store = FileStore(kb_path)
vector_index = VectorIndex(kb_path)
bm25_index = BM25Index(f"{kb_path}/index/bm25.db")

# 2. 添加并索引文档
for file_path in Path("docs").rglob("*.md"):
    doc_id = store.add_file(file_path)
    doc = store.get_file(doc_id)
    if doc:
        vector_index.index_document(doc)
        bm25_index.index_document(doc)
        print(f"Indexed: {doc.file_name}")

# 3. 创建检索器
retriever = Retriever(store, vector_index, bm25_index)

# 4. 搜索
results = retriever.retrieve("如何使用装饰器", top_k=5)

for i, r in enumerate(results, 1):
    print(f"\n--- Result {i} ---")
    print(f"File: {r.chunk.metadata['file_name']}")
    print(f"Score: {r.score:.3f}")
    print(f"Source: {r.chunk.metadata.get('search_source', 'unknown')}")
    print(f"Content: {r.chunk.content[:200]}...")
```
