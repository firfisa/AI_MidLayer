# AI MidLayer 待完善计划 (Backlog)

> 在完成初步完整框架后再进行这些计划

---

## Phase 1 增强 (后续完善)

### 📄 文件解析增强
- [ ] 集成 Unstructured.io 完整解析
  - PDF 高质量解析
  - DOCX/PPTX 支持
  - 图片 OCR
  - 表格识别
- [ ] 多模态内容处理
  - 图片描述生成
  - 代码语法高亮

### 🔍 向量索引增强
- [ ] 集成真正的 Embedding 模型
  - 支持 OpenAI / BGE / 本地模型
  - 配置化选择
- [ ] 混合检索
  - 关键词索引 (BM25)
  - 向量相似度 + 关键词融合排序
- [ ] 分块策略优化
  - 按语义段落分块
  - 标题层级感知

### 🖥️ CLI 增强
- [ ] `midlayer chat` - 交互式对话
- [ ] `midlayer export` - 导出标准化 Context
- [ ] 进度条显示
- [ ] 彩色日志级别

---

## Phase 2 增强 (后续完善)

### 🤖 Agent 架构增强
- [ ] 完整 Reflexion 循环
  - 多轮自我修正
  - 错误恢复策略
- [ ] Tool 使用能力
  - 文件操作 Tool
  - 网络请求 Tool
  - 代码执行 Tool
- [ ] Agent 缓存
  - 分析结果缓存
  - 避免重复计算

### 🔗 Orchestrator 增强
- [ ] 并行执行支持
- [ ] 条件分支路由
- [ ] 错误重试和回滚
- [ ] 执行状态持久化

### 📊 结构识别增强
- [ ] 更多文档类型
  - API 文档
  - 日志文件
  - 配置文件深度解析
- [ ] 关系图谱
  - 文档间引用关系
  - 代码调用关系

---

## LLM 集成增强 (后续完善)

### 🧠 模型支持
- [ ] 流式输出 (Streaming)
- [ ] 多模态支持 (Vision)
- [ ] 函数调用 (Function Calling)
- [ ] 模型切换热加载

### 💰 成本控制
- [ ] Token 使用统计
- [ ] 调用频率限制
- [ ] 模型降级策略

### 🔒 安全增强
- [ ] API Key 加密存储
- [ ] 敏感信息过滤
- [ ] 审计日志

---

## QMD 技术集成增强 (后续完善)

> 借鉴 [QMD](https://github.com/tobi/qmd) 项目的高级技术

### ⭐⭐⭐ 高优先级

- [x] **CLI 混合搜索集成** ✅ 82 tests
  - `midlayer search --hybrid/--no-hybrid`
  - `midlayer add` 双索引 (Vector + BM25)
  - 搜索来源颜色区分显示
  - `--verbose` 显示 RRF 分数

- [x] **端到端混合搜索测试** ✅ 7 tests
  - 真实文档的混合搜索验证
  - BM25 vs Vector vs Hybrid 对比
  - 中文内容索引测试

### ⭐⭐ 中优先级

- [ ] **异步并行搜索**
  - BM25 和 Vector 并行执行
  - asyncio 优化检索性能

- [ ] **重排序模型选择**
  - 支持多种重排序策略
  - 无 LLM 时使用 Cross-encoder 本地模型
  - 配置化选择重排序方式

### ⭐ 低优先级 (框架完成后)

- [ ] **模型微调接口**
  - 预留本地小模型微调能力
  - Query Expansion 模型训练数据生成
  - 支持 GGUF 格式模型加载
  - 参考 QMD 的 `finetune/` 目录

- [ ] **MCP 协议支持**
  - Model Context Protocol 集成
  - 让 Claude/Cursor 等 AI 工具调用 MidLayer

- [ ] **评估驱动开发**
  - 搜索质量自动评估
  - 召回率/准确率测试集
  - 参考 QMD 的 `test/eval-harness.ts`

---

## Phase 3 增强: RAG 用户体验

### 📱 用户体验
- [ ] 进度条和状态显示
- [ ] 彩色日志输出
- [ ] 配置文件支持 (.midlayer.yaml)

---

## 设计原则 (必须遵守)

> **高内聚低耦合、模块分离、可扩展性**

1. **单一职责**: 每个类/模块只做一件事
2. **接口抽象**: 核心组件定义抽象接口，具体实现可替换
3. **依赖注入**: 组件通过构造函数接收依赖，而非内部创建
4. **插件化架构**: Agent、Index、Retriever 都可插拔替换
5. **配置驱动**: 关键参数通过配置文件控制，不硬编码

---

## 架构约束

```
ai_midlayer/
├── agents/           # 高内聚：所有 Agent 逻辑
│   ├── base.py       # 抽象基类
│   ├── parser.py     # 文件解析
│   ├── structure.py  # 结构识别
│   └── llm_agent.py  # LLM 增强
├── knowledge/        # 高内聚：知识管理
│   ├── models.py     # 数据模型
│   ├── store.py      # 存储
│   ├── index.py      # 索引
│   └── retriever.py  # 检索
├── orchestrator/     # 编排层
│   └── __init__.py   # Pipeline
├── llm/              # LLM 适配器
│   └── __init__.py   # LiteLLM
├── cli/              # 接口层
└── config.py         # 配置管理
```

低耦合：各模块通过接口通信，不直接依赖实现细节
