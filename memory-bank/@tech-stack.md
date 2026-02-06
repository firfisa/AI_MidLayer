# AI MidLayer 技术栈

> 基于 Vibe Coding 方法论，选择最简单但最健壮的技术栈

## 核心技术选型

| 层级 | 技术 | 理由 |
|------|------|------|
| **语言** | Python 3.11+ | 生态丰富，AI/ML 首选 |
| **Agentic 框架** | LangGraph | 成熟稳定，状态管理强 |
| **LLM 调用** | LiteLLM | 统一接口，支持多模型 |
| **向量数据库** | LanceDB | 嵌入式、零配置、本地优先 |
| **文件解析** | Unstructured.io | 多格式支持，开源 |
| **CLI** | Typer | 简洁优雅，类型提示友好 |
| **配置管理** | Pydantic | 类型安全，验证强大 |

## 项目结构

```
ai-midlayer/
├── memory-bank/              # Vibe Coding 记忆库
│   ├── @architecture.md      # 架构说明（AI 必读）
│   ├── @tech-stack.md        # 技术栈（本文件）
│   ├── @implementation-plan.md
│   └── @progress.md          # 进度记录
├── src/
│   └── ai_midlayer/
│       ├── __init__.py
│       ├── cli/              # CLI 入口
│       ├── agents/           # 各类 Agent
│       ├── knowledge/        # 知识库模块
│       └── utils/            # 工具函数
├── tests/
├── pyproject.toml
└── README.md
```

## 依赖清单

```toml
[project]
dependencies = [
    "langgraph>=0.2",
    "litellm>=1.0",
    "lancedb>=0.5",
    "unstructured>=0.10",
    "typer>=0.12",
    "pydantic>=2.0",
    "rich>=13.0",
]
```

## 环境要求

- Python 3.11+
- 至少一个 LLM API Key（OpenAI / Claude / DeepSeek）
