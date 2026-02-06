# AI MidLayer 架构说明

> ⚠️ **AI 必读**：写任何代码前必须完整阅读本文档

## 项目目标

构建一个「大模型上下文中间层」，让知识工作者能够以最小认知负担，将杂乱项目资料转化为高质量上下文。

## 核心问题

**信息不对齐** — AI 需要的信息与用户已知/已有的信息之间存在鸿沟。

## 系统分层

```
L5: 用户接口层 (CLI)
    ↓
L4: 编排层 (Orchestrator)
    ↓
L3: Agent 层 (Processing Agents)
    ↓
L2: 知识层 (Knowledge Layer)
    ↓
L1: 基础设施层 (LLM + Vector DB)
```

## Phase 1 范围

- [ ] 知识库基础结构（无损存储 + 向量索引）  
- [ ] 文件解析 Agent（单轮处理）
- [ ] 简易 RAG 检索
- [ ] CLI 界面

## 核心模块

### 1. 知识库 (`src/ai_midlayer/knowledge/`)

| 文件 | 职责 |
|------|------|
| `store.py` | 无损文件存储 |
| `index.py` | 向量索引管理 |
| `retriever.py` | RAG 检索器 |

### 2. Agent (`src/ai_midlayer/agents/`)

| 文件 | 职责 |
|------|------|
| `parser.py` | 文件解析 Agent |
| `base.py` | Agent 基类（OODA + Reflexion 循环）|

### 3. CLI (`src/ai_midlayer/cli/`)

| 文件 | 职责 |
|------|------|
| `main.py` | CLI 入口 |
| `commands.py` | 命令定义 |

## 设计原则（Vibe Coding）

1. **接口先行，实现后补**
2. **一次只改一个模块**
3. **每步都要有验证测试**
4. **文档即上下文，不是事后补**
