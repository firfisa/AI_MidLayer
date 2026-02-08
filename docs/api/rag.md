# RAG 模块 API

> 检索增强生成 (Retrieval-Augmented Generation) 核心模块

## 概览

RAG 模块负责：
- 查询引擎 (`RAGQueryEngine`)
- 结果融合 (`reciprocal_rank_fusion`)
- LLM 重排序 (`LLMReranker`)
- 查询扩展 (`LLMQueryExpander`, `HyDE`)

---

## RAGQueryEngine

RAG 查询引擎，结合检索和生成。

### 初始化

```python
from ai_midlayer.rag.query import RAGQueryEngine
from ai_midlayer.llm import LiteLLMClient

llm = LiteLLMClient(model="gpt-4o-mini")
rag = RAGQueryEngine(retriever, llm)
```

### 方法

#### query

单次问答。

```python
answer = rag.query(
    question="这个项目的主要功能是什么？",
    top_k=5,        # 检索文档数
    max_tokens=512, # 回答最大长度
)
print(answer)
```

**流程:**
1. 检索相关文档
2. 构建上下文
3. 调用 LLM 生成回答

#### create_session

创建对话会话 (支持多轮对话)。

```python
session = rag.create_session()

# 多轮对话，自动记住历史
answer1 = session.chat("项目架构是什么？")
answer2 = session.chat("详细说说检索模块")  # 记住上下文
answer3 = session.chat("它和 BM25 有什么关系？")

# 获取历史
history = session.history
```

---

## RAGSession

对话会话，维护对话历史。

### 方法

#### chat

多轮对话。

```python
answer = session.chat("问题")
```

#### clear_history

清除历史。

```python
session.clear_history()
```

### 属性

```python
session.history     # list[Message]
session.retriever   # Retriever
session.llm         # LLM client
```

---

## 结果融合 (fusion.py)

### reciprocal_rank_fusion

RRF 融合算法，合并多个搜索结果列表。

```python
from ai_midlayer.rag.fusion import reciprocal_rank_fusion

# 合并 BM25 和 Vector 结果
fused = reciprocal_rank_fusion(
    result_lists=[bm25_results, vector_results],
    weights=[2.0, 1.0],  # BM25 权重更高
    top_n=10,
    k=60,  # RRF 参数
)

for fr in fused:
    print(f"RRF Score: {fr.rrf_score:.3f}")
    print(f"Sources: {fr.sources}")  # ['bm25', 'vector'] 或 ['bm25']
    print(f"Content: {fr.result.chunk.content[:100]}")
```

**参数:**
| 参数 | 说明 |
|------|------|
| `result_lists` | 多个 SearchResult 列表 |
| `weights` | 每个列表的权重 |
| `top_n` | 返回结果数 |
| `k` | RRF 常数 (默认 60) |

**返回:** `list[FusionResult]`

### detect_strong_signal

检测 BM25 强信号 (精确匹配)。

```python
from ai_midlayer.rag.fusion import detect_strong_signal

signal = detect_strong_signal(bm25_results)

if signal.is_strong:
    print(f"强信号! 原因: {signal.reason}")
    # 跳过融合，直接使用 BM25 结果
```

### position_aware_blend

位置感知混合。

```python
from ai_midlayer.rag.fusion import position_aware_blend

blended = position_aware_blend(
    bm25_results,
    vector_results,
    bm25_weight=0.6,  # BM25 权重
)
```

---

## LLM 重排序 (reranker.py)

### LLMReranker

使用 LLM 对搜索结果重新排序。

```python
from ai_midlayer.rag.reranker import LLMReranker

reranker = LLMReranker(llm)

reranked = reranker.rerank(
    query="Python 装饰器",
    results=search_results,
    top_k=3,
)
```

**流程:**
1. 让 LLM 给每个结果打分 (0-10)
2. 按分数重新排序
3. 返回 top_k 结果

### ScoreBasedReranker

基于简单规则的重排序器。

```python
from ai_midlayer.rag.reranker import ScoreBasedReranker

reranker = ScoreBasedReranker()
reranked = reranker.rerank(query, results, top_k=5)
```

---

## 查询扩展 (expansion.py)

### LLMQueryExpander

使用 LLM 扩展查询。

```python
from ai_midlayer.rag.expansion import LLMQueryExpander

expander = LLMQueryExpander(llm)

expanded = expander.expand("Python 装饰器")
# ExpandedQuery(
#     original="Python 装饰器",
#     expansions=["Python decorator pattern", "函数包装器", "@语法"],
#     hyde_doc=None,
# )
```

### SimpleQueryExpander

简单规则扩展。

```python
from ai_midlayer.rag.expansion import SimpleQueryExpander

expander = SimpleQueryExpander()
expanded = expander.expand("how to use decorator?")
# 移除问号，添加同义词
```

### HyDE (Hypothetical Document Embedding)

假设文档嵌入。

```python
from ai_midlayer.rag.expansion import LLMQueryExpander

expander = LLMQueryExpander(llm, use_hyde=True)

expanded = expander.expand("Python 装饰器怎么用")
# 生成假设的答案文档用于检索
print(expanded.hyde_doc)
```

---

## ExpandedQuery

```python
from ai_midlayer.rag.expansion import ExpandedQuery

eq = ExpandedQuery(
    original="query",
    expansions=["expansion1", "expansion2"],
    hyde_doc="假设文档内容...",
)

# 获取所有查询
all_queries = eq.get_all_queries()  # [original, exp1, exp2]

# 获取 BM25 查询
bm25_queries = eq.get_bm25_queries()  # 不包含 HyDE

# 获取向量查询
vector_queries = eq.get_vector_queries()  # 可能包含 HyDE
```

---

## 使用示例

### 完整 RAG 流程

```python
from ai_midlayer.knowledge.retriever import Retriever
from ai_midlayer.rag.query import RAGQueryEngine
from ai_midlayer.rag.reranker import LLMReranker
from ai_midlayer.rag.expansion import LLMQueryExpander
from ai_midlayer.llm import LiteLLMClient

# 初始化
llm = LiteLLMClient(model="deepseek-chat", base_url="https://api.deepseek.com/v1")
retriever = Retriever(store, vector_index, bm25_index)

# 可选：查询扩展
expander = LLMQueryExpander(llm, use_hyde=True)

# 可选：重排序
reranker = LLMReranker(llm)

# RAG 引擎
rag = RAGQueryEngine(
    retriever=retriever,
    llm=llm,
    expander=expander,      # 可选
    reranker=reranker,      # 可选
)

# 问答
answer = rag.query("这个项目如何实现混合搜索？")
print(answer)
```

### 多轮对话

```python
session = rag.create_session()

print("开始对话 (输入 'quit' 退出)")
while True:
    user_input = input("You: ")
    if user_input.lower() == 'quit':
        break
    
    answer = session.chat(user_input)
    print(f"AI: {answer}\n")
```
