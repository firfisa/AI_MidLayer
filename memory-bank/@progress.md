# AI MidLayer 开发进度

> 记录每个步骤的完成情况，供后续开发参考

## 进度概览

| 步骤 | 状态 | 完成时间 |
|------|------|---------|
| Step 1: 项目初始化 | ✅ 完成 | 2026-02-06 |
| Step 2: 无损存储 | ✅ 完成 | 2026-02-06 |
| Step 3: 向量索引 | ⏸️ 待开始 | - |
| Step 4: 文件解析 Agent | ✅ 基础完成 | 2026-02-06 |
| Step 5: RAG 检索器 | ⏸️ 待开始 | - |
| Step 6: CLI 界面 | ✅ 基础完成 | 2026-02-06 |

---

## 详细记录

### Step 1: 项目初始化 ✅

**完成时间**: 2026-02-06

**完成的工作**:
- [x] 创建 memory-bank 结构 (`@architecture.md`, `@tech-stack.md`, `@implementation-plan.md`, `@progress.md`)
- [x] 创建项目骨架 (`pyproject.toml`, `src/ai_midlayer/`)
- [x] 使用 conda 创建 `midlayer` 虚拟环境 (Python 3.11)
- [x] 安装依赖 (langgraph, litellm, lancedb, unstructured, typer, pydantic)
- [x] 运行测试验证 (9/9 通过)

**测试结果**:
```
tests/test_agents.py::TestParserAgent::test_parse_markdown PASSED
tests/test_agents.py::TestParserAgent::test_parse_text PASSED
tests/test_agents.py::TestParserAgent::test_parse_nonexistent PASSED
tests/test_knowledge.py::TestDocument::test_from_file_text PASSED
tests/test_knowledge.py::TestDocument::test_from_file_missing PASSED
tests/test_knowledge.py::TestFileStore::test_add_and_get_file PASSED
tests/test_knowledge.py::TestFileStore::test_list_files PASSED
tests/test_knowledge.py::TestFileStore::test_remove_file PASSED
tests/test_knowledge.py::TestFileStore::test_remove_nonexistent PASSED
============================== 9 passed ==============================
```

**CLI 命令可用**:
- `midlayer init` - 初始化知识库
- `midlayer add <file>` - 添加文件
- `midlayer status` - 查看状态
- `midlayer search <query>` - 搜索（待实现向量索引）
- `midlayer remove <id>` - 删除文件

---

### Step 2: 无损存储 ✅

**完成时间**: 2026-02-06

**完成的工作**:
- [x] `Document` 数据模型 (Pydantic)
- [x] `Chunk` 数据模型
- [x] `FileStore` 类：add_file, get_file, list_files, remove_file
- [x] 原始文件保留在 `raw/` 目录
- [x] 解析后的 JSON 保存在 `parsed/` 目录

---

### Step 3: 向量索引 ✅

**完成时间**: 2026-02-06

**完成的工作**:
- [x] `VectorIndex` 类使用 LanceDB
  - `_chunk_text()` - 智能分块（句子边界）
  - `index_document()` - 索引文档
  - `search()` - 语义搜索
  - `remove_document()` - 删除文档索引
  - `get_stats()` - 索引统计
- [x] `Retriever` 类整合 FileStore + VectorIndex
  - `retrieve()` - RAG 检索
  - `get_full_document()` - 无损原始内容
- [x] CLI 集成
  - `add` 命令现在自动索引
  - `search` 命令使用语义搜索
  - `status` 显示索引统计

**测试结果**:
```
17 passed in 0.87s
```

---

*后续步骤完成后在此追加记录*

---

## Phase 2: Agentic 增强 ✅

**完成时间**: 2026-02-06

**设计原则**: 高内聚低耦合、模块分离、可扩展性

### 架构重构

**新增模块**:

| 文件 | 说明 |
|------|------|
| `agents/protocols.py` | Protocol 接口定义（AgentState, LLMProvider, Tool, AgentCallback） |
| `agents/base.py` | BaseAgent 基类（OODA + Reflexion 循环，依赖注入，回调） |
| `agents/parser.py` | ParserAgent 重构（实现完整 OODA 循环） |
| `agents/structure.py` | StructureAgent 新增（文档类型识别、结构解析） |
| `orchestrator/__init__.py` | Pipeline 编排层（顺序执行、上下文传递） |

**核心特性**:
- ✅ OODA 循环: Observe → Orient → Decide → Act
- ✅ Reflexion: Reflect → Refine 自我修正
- ✅ 依赖注入: LLM Provider、Tools、Callbacks 可配置
- ✅ Protocol 模式: 结构化子类型，接口可替换
- ✅ 文档类型识别: 自动分类（技术文档、会议记录等）
- ✅ 结构解析: Markdown 标题、代码函数/类、文本段落

**测试结果**:
```
24 passed in 0.88s
```

---

## LLM 集成 ✅

**完成时间**: 2026-02-06

### 新增模块

| 文件 | 说明 |
|------|------|
| `llm/__init__.py` | LiteLLM 适配器（多提供商支持） |
| `config.py` | 配置管理（环境变量、配置文件） |
| `agents/llm_agent.py` | LLMAgentMixin（LLM 增强能力） |

### 支持的提供商
- OpenAI (GPT-4, GPT-3.5)
- Anthropic (Claude)
- Google (Gemini)
- Ollama (本地模型)
- **自定义 API** (DeepSeek, Moonshot 等 OpenAI 兼容接口)

### 配置方式
```bash
export MIDLAYER_LLM_PROVIDER="custom"
export MIDLAYER_LLM_MODEL="deepseek-reasoner"
export MIDLAYER_BASE_URL="https://api.deepseek.com"
export MIDLAYER_API_KEY="your-api-key"
```

### 端到端测试结果
```
Phase 1 (ParserAgent): ✅ 成功 - md 文件，质量分数 1.0
Phase 2 (StructureAgent): ✅ 成功 - technical_doc, 4 章节
LLM (DeepSeek): ✅ 成功 - Orient 分析返回正确结果
```

**测试结果**:
```
37 passed, 2 skipped in 0.68s
```

---

## Phase 3: RAG 查询与用户体验 ✅

**完成时间**: 2026-02-06

### 新增模块

| 文件 | 说明 |
|------|------|
| `rag/__init__.py` | RAGQuery, ConversationRAG |
| `cli/main.py` | 新增 `chat`, `ask` 命令 |
| `knowledge/models.py` | 增强 SearchResult (file_name, content 属性) |

### 核心功能

1. **RAG 查询流程**
   - 检索：语义相似度搜索 top-k 文档
   - 构建上下文：合并 chunks + 元数据
   - LLM 生成：基于上下文回答问题
   - 返回来源：引用相关文档

2. **CLI 命令**
   - `midlayer chat` - 交互式多轮对话
   - `midlayer ask "问题"` - 单次查询
   - 显示来源和 Token 使用统计

### 端到端测试结果
```
问题: AI MidLayer 有什么功能?
回答: 根据提供的资料，AI MidLayer 的核心功能包括：
1. 文件解析和索引
2. 语义搜索
3. RAG 查询（检索增强生成）
4. Agentic OODA 循环
[来源: readme.md]
Token 使用: 391 tokens
```

**测试结果**:
```
46 passed, 2 skipped in 0.96s
```

---

## QMD 技术集成：混合搜索增强 ✅

**完成时间**: 2026-02-07

### 借鉴 QMD 的核心技术

| 技术 | 说明 | 实现文件 |
|------|------|---------|
| **BM25 索引** | SQLite FTS5 全文检索 | `knowledge/bm25.py` |
| **RRF 融合** | 倒数排名融合，原查询权重 ×2 | `rag/fusion.py` |
| **位置感知混合** | 动态调整 RRF/Rerank 权重 | `rag/fusion.py` |
| **强信号检测** | 跳过扩展的优化 | `rag/fusion.py` |
| **混合检索器** | 结合 Vector + BM25 | `knowledge/hybrid.py` |

### 新增模块

```
src/ai_midlayer/
├── knowledge/
│   ├── bm25.py          # BM25 索引 (SQLite FTS5)
│   └── hybrid.py        # HybridRetriever
└── rag/
    └── fusion.py        # RRF 融合算法
```

### 核心算法

**RRF 融合公式**:
```python
score = weight / (k + rank + 1)
# k=60, 原查询权重 x2
# 榜首奖励: +0.05 (第1名), +0.02 (第2-3名)
```

**位置感知混合**:
```
Top 1-3:  75% RRF + 25% Rerank (信任精确匹配)
Top 4-10: 60% RRF + 40% Rerank
Top 11+:  40% RRF + 60% Rerank (信任语义)
```

**测试结果**:
```
59 passed, 2 skipped in 0.62s
```

### Phase 3: LLM 重排序

| 模块 | 说明 |
|------|------|
| `rag/reranker.py` | LLMReranker, ScoreBasedReranker, NoOpReranker |

**核心功能**:
- Cross-encoder 式 LLM 打分
- 位置感知混合 (position_aware_blend)
- 关键词密度规则打分
- 优雅的 LLM 失败降级

### Phase 4: 查询扩展 + HyDE

| 模块 | 说明 |
|------|------|
| `rag/expansion.py` | LLMQueryExpander, SimpleQueryExpander, NoOpExpander |

**扩展类型**:
- `lex`: 关键词同义词 (用于 BM25)
- `vec`: 语义句子 (用于 Vector)
- `hyde`: 假设文档 (HyDE 技术)

**测试结果**:
```
75 passed, 2 skipped in 0.75s
```

---

## CLI 混合搜索集成 ✅

**完成时间**: 2026-02-07

### 新增功能

| 功能 | 说明 |
|------|------|
| `midlayer add` | 双索引 (Vector + BM25) |
| `midlayer search --hybrid` | 混合搜索 (默认开启) |
| `midlayer search --no-hybrid` | 仅向量搜索 |
| `midlayer search -v` | 详细模式显示 RRF 分数 |

### 搜索来源显示

| 边框颜色 | 含义 |
|----------|------|
| 🟢 绿色 | 混合搜索 (RRF 融合) |
| 🟡 黄色 | BM25 精确匹配 |
| 🔵 蓝色 | 向量语义搜索 |

### E2E 测试覆盖

- 混合检索创建与配置
- Python/JavaScript/API 文档搜索
- 精确关键词匹配 (reset_password)
- 语义搜索降级
- 混合/向量对比
- 强制模式切换
- 中文内容索引

**测试结果**:
```
82 passed, 2 skipped in 0.61s
```
