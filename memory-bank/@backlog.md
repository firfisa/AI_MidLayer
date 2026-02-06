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
│   └── structure.py  # 结构识别 (Phase 2)
├── knowledge/        # 高内聚：知识管理
│   ├── models.py     # 数据模型
│   ├── store.py      # 存储
│   ├── index.py      # 索引
│   └── retriever.py  # 检索
├── orchestrator/     # Phase 2 新增
│   └── pipeline.py   # 编排层
├── cli/              # 接口层
└── config/           # 配置管理
```

低耦合：各模块通过接口通信，不直接依赖实现细节
