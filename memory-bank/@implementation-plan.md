# AI MidLayer 实施计划

> 基于 Vibe Coding 方法论，每步小而具体，必须包含验证测试

## Phase 1: 核心管线

### Step 1: 项目初始化 ✅ 待开始

**目标**: 创建项目骨架，配置开发环境

**任务**:
1. 创建项目目录结构
2. 设置 `pyproject.toml`
3. 创建虚拟环境并安装依赖
4. 验证所有依赖可正常导入

**验证测试**:
```bash
python -c "import langgraph, litellm, lancedb, typer; print('✅ 依赖安装成功')"
```

---

### Step 2: 知识库 - 无损存储 ⏳ 待开始

**目标**: 实现文件的无损存储和元数据管理

**任务**:
1. 定义 `Document` 数据模型（Pydantic）
2. 实现 `FileStore` 类：
   - `add_file(path)` - 添加文件到知识库
   - `get_file(doc_id)` - 获取文件
   - `list_files()` - 列出所有文件

**验证测试**:
```python
def test_file_store():
    store = FileStore("./test_kb")
    doc_id = store.add_file("test.md")
    assert store.get_file(doc_id) is not None
    assert len(store.list_files()) == 1
```

---

### Step 3: 知识库 - 向量索引 ⏳ 待开始

**目标**: 使用 LanceDB 实现向量索引

**任务**:
1. 实现 `VectorIndex` 类：
   - `index_document(doc)` - 索引文档
   - `search(query, top_k)` - 语义搜索
2. 集成 embedding 模型

**验证测试**:
```python
def test_vector_search():
    index = VectorIndex("./test_kb")
    index.index_document(doc)
    results = index.search("测试查询", top_k=3)
    assert len(results) > 0
```

---

### Step 4: 文件解析 Agent ⏳ 待开始

**目标**: 实现基础文件解析功能

**任务**:
1. 定义 `Agent` 基类（OODA 循环骨架）
2. 实现 `ParserAgent`：
   - 支持 Markdown、TXT、PDF
   - 输出结构化 Document 对象

**验证测试**:
```python
def test_parser_agent():
    agent = ParserAgent()
    doc = agent.parse("test.pdf")
    assert doc.content is not None
    assert doc.metadata["file_type"] == "pdf"
```

---

### Step 5: RAG 检索器 ⏳ 待开始

**目标**: 整合存储和索引，实现 RAG 检索

**任务**:
1. 实现 `Retriever` 类：
   - `retrieve(query)` - 返回相关内容片段
   - 支持混合检索（向量 + 关键词）

**验证测试**:
```python
def test_retriever():
    retriever = Retriever(store, index)
    chunks = retriever.retrieve("关键问题")
    assert all(chunk.source_file for chunk in chunks)
```

---

### Step 6: CLI 界面 ⏳ 待开始

**目标**: 提供基础命令行交互

**命令**:
- `midlayer init` - 初始化项目知识库
- `midlayer add <file>` - 添加文件
- `midlayer search <query>` - 搜索知识库
- `midlayer status` - 查看知识库状态

**验证测试**:
```bash
midlayer init
midlayer add test.md
midlayer search "测试"
# 应返回相关结果
```

---

## 完成标准

Phase 1 完成时，用户应能：
1. 通过 CLI 创建项目知识库
2. 添加多种格式的文件
3. 通过自然语言查询获取相关内容
