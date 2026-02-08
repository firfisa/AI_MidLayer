# AI MidLayer 文档

## 📚 文档目录

### 快速开始

- [快速入门指南](guides/quickstart.md) - 5 分钟上手

### API 参考

- [Knowledge 模块](api/knowledge.md) - 文档存储、索引、检索
  - FileStore - 文档管理
  - VectorIndex - 向量索引
  - BM25Index - 关键词索引
  - Retriever - 混合检索
  - EmbeddingClient - 嵌入生成

- [RAG 模块](api/rag.md) - 检索增强生成
  - RAGQueryEngine - 查询引擎
  - Fusion - 结果融合
  - Reranker - 重排序
  - Query Expansion - 查询扩展

- [LLM 模块](api/llm.md) - 语言模型适配
  - LiteLLMClient - 统一 LLM 接口

- [CLI 命令](api/cli.md) - 命令行工具
  - init, add, search, ask, chat...

### 架构设计

- [系统架构](architecture/overview.md) - 整体设计
  - 分层架构
  - 核心设计决策
  - 目录结构

### 其他资源

- [项目 README](../README.md)
- [Memory Bank](../memory-bank/) - 项目记忆文档
  - [@architecture.md](../memory-bank/@architecture.md)
  - [@tech-stack.md](../memory-bank/@tech-stack.md)
  - [@progress.md](../memory-bank/@progress.md)

---

## 📝 文档维护说明

本文档通过 `docs/` 目录管理，遵循以下结构：

```
docs/
├── index.md              # 本文件 - 文档索引
├── api/                  # API 参考
│   ├── cli.md
│   ├── knowledge.md
│   ├── llm.md
│   └── rag.md
├── guides/               # 使用指南
│   └── quickstart.md
└── architecture/         # 架构设计
    └── overview.md
```

### 更新文档

当添加新功能时，请相应更新：

1. **新 API** → 更新对应的 `docs/api/*.md`
2. **新命令** → 更新 `docs/api/cli.md`
3. **架构变更** → 更新 `docs/architecture/overview.md`
4. **新指南** → 添加到 `docs/guides/`

### 自动同步 (推荐)

使用 workflow 命令自动更新文档：

```bash
# 运行文档同步 workflow
/sync-docs
```

这会自动：
1. 检查代码变更
2. 更新相关文档
3. 生成 changelog

---

## 🔗 链接

- [GitHub 仓库](https://github.com/yourusername/ai-midlayer)
- [问题反馈](https://github.com/yourusername/ai-midlayer/issues)
