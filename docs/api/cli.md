# CLI 命令参考

> midlayer 命令行工具使用指南

## 概览

```bash
midlayer [COMMAND] [OPTIONS]
```

## 命令列表

| 命令 | 说明 |
|------|------|
| `init` | 初始化知识库 |
| `add` | 添加文件到知识库 |
| `search` | 搜索知识库 |
| `ask` | 单次问答 |
| `chat` | 交互式对话 |
| `list` | 列出知识库中的文件 |
| `remove` | 删除文件 |
| `stats` | 显示统计信息 |

---

## init

初始化知识库目录。

```bash
midlayer init [--path PATH]
```

**选项:**
| 选项 | 说明 | 默认值 |
|------|------|--------|
| `--path`, `-p` | 知识库路径 | `.midlayer` |

**示例:**
```bash
# 当前目录初始化
midlayer init

# 指定路径
midlayer init --path ~/my-knowledge
```

---

## add

添加文件到知识库 (自动双索引: Vector + BM25)。

```bash
midlayer add PATH [--kb PATH]
```

**参数:**
| 参数 | 说明 |
|------|------|
| `PATH` | 文件或目录路径 |

**选项:**
| 选项 | 说明 | 默认值 |
|------|------|--------|
| `--kb` | 知识库路径 | `.midlayer` |

**示例:**
```bash
# 添加单个文件
midlayer add README.md

# 添加目录 (递归)
midlayer add docs/

# 添加代码文件
midlayer add src/

# 指定知识库
midlayer add paper.pdf --kb ~/research-kb
```

**输出:**
```
📁 Adding directory: docs/
  ✓ Added: api.md (a1b2c3d4, 5v/5b chunks)
  ✓ Added: guide.md (e5f6g7h8, 3v/3b chunks)

✅ Added 2 files (Vector: 8, BM25: 8)
```

---

## search

搜索知识库 (默认使用混合搜索)。

```bash
midlayer search QUERY [OPTIONS]
```

**参数:**
| 参数 | 说明 |
|------|------|
| `QUERY` | 搜索查询 |

**选项:**
| 选项 | 说明 | 默认值 |
|------|------|--------|
| `--kb` | 知识库路径 | `.midlayer` |
| `--limit`, `-n` | 返回结果数 | `5` |
| `--hybrid/--no-hybrid` | 启用/禁用混合搜索 | `--hybrid` |
| `--verbose`, `-v` | 显示详细信息 | `False` |

**示例:**
```bash
# 基本搜索
midlayer search "Python 装饰器"

# 限制结果数
midlayer search "API authentication" -n 3

# 仅向量搜索
midlayer search "语义相似的内容" --no-hybrid

# 详细模式 (显示 RRF 分数和搜索来源)
midlayer search "error code 401" -v
```

**输出:**
```
🔍 Searching (hybrid): Python 装饰器

┌─────────────────────────────────────────────────────────────┐
│ [1] python_decorators.md (score: 0.95)                      │
│─────────────────────────────────────────────────────────────│
│ # Python Decorators                                         │
│                                                             │
│ Decorators are functions that modify the behavior of...    │
└─────────────────────────────────────────────────────────────┘
```

**搜索来源颜色:**
| 边框颜色 | 含义 |
|----------|------|
| 🟢 绿色 | 混合搜索 (RRF 融合) |
| 🟡 黄色 | BM25 精确匹配 (强信号) |
| 🔵 蓝色 | 向量语义搜索 |

---

## ask

单次问答 (检索 + 生成)。

```bash
midlayer ask QUESTION [OPTIONS]
```

**参数:**
| 参数 | 说明 |
|------|------|
| `QUESTION` | 问题 |

**选项:**
| 选项 | 说明 | 默认值 |
|------|------|--------|
| `--kb` | 知识库路径 | `.midlayer` |
| `--limit`, `-n` | 检索文档数 | `5` |

**示例:**
```bash
midlayer ask "这个项目的主要功能是什么？"
midlayer ask "如何配置 LLM？" -n 3
```

**注意:** 需要配置 LLM API (见 [配置](#环境变量))。

---

## chat

交互式对话 (支持多轮，带历史记忆)。

```bash
midlayer chat [OPTIONS]
```

**选项:**
| 选项 | 说明 | 默认值 |
|------|------|--------|
| `--kb` | 知识库路径 | `.midlayer` |

**示例:**
```bash
midlayer chat
```

**交互:**
```
🤖 AI MidLayer Chat (输入 'quit' 退出)

You: 项目架构是什么？
AI: 这个项目采用分层架构...

You: 详细说说检索模块
AI: 检索模块包含以下组件...
```

**快捷命令:**
| 命令 | 说明 |
|------|------|
| `quit` / `exit` | 退出对话 |
| `clear` | 清除历史 |
| `history` | 显示对话历史 |

---

## list

列出知识库中的所有文件。

```bash
midlayer list [--kb PATH]
```

**示例:**
```bash
midlayer list
```

**输出:**
```
📚 Knowledge Base: .midlayer

ID        | File Name              | Type     | Chunks
----------|------------------------|----------|-------
a1b2c3d4  | README.md              | markdown | 5
e5f6g7h8  | api_guide.md           | markdown | 12
i9j0k1l2  | config.py              | python   | 3

Total: 3 files, 20 chunks
```

---

## remove

从知识库删除文件。

```bash
midlayer remove DOC_ID [--kb PATH]
```

**参数:**
| 参数 | 说明 |
|------|------|
| `DOC_ID` | 文档 ID (可用 `list` 查看) |

**示例:**
```bash
midlayer remove a1b2c3d4
```

---

## stats

显示知识库统计信息。

```bash
midlayer stats [--kb PATH]
```

**输出:**
```
📊 Knowledge Base Statistics

Path: .midlayer
Documents: 15
Chunks: 120
Embedding Model: text-embedding-3-small
Use API: True
BM25 Index: Yes
```

---

## 环境变量配置

在使用需要 LLM 的命令 (`ask`, `chat`) 前需配置：

```bash
# ~/.zshrc 或 ~/.bashrc

# LLM 配置
export MIDLAYER_API_KEY="sk-xxx"
export MIDLAYER_BASE_URL="https://api.openai.com/v1"  # 可选
export MIDLAYER_LLM_MODEL="gpt-4o-mini"

# 嵌入模型配置 (可选，使用 add 时生效)
export MIDLAYER_EMBEDDING_MODEL="text-embedding-3-small"
export MIDLAYER_EMBEDDING_API_KEY="sk-xxx"
export MIDLAYER_EMBEDDING_BASE_URL="https://api.openai.com/v1"
```

**常用配置:**

```bash
# OpenAI
export MIDLAYER_API_KEY="sk-xxx"
export MIDLAYER_LLM_MODEL="gpt-4o-mini"

# DeepSeek (推荐，性价比高)
export MIDLAYER_API_KEY="sk-xxx"
export MIDLAYER_BASE_URL="https://api.deepseek.com/v1"
export MIDLAYER_LLM_MODEL="deepseek-chat"

# 国内代理
export MIDLAYER_API_KEY="sk-xxx"
export MIDLAYER_BASE_URL="https://your-proxy.com/v1"
export MIDLAYER_LLM_MODEL="gpt-4o"
```

---

## 使用示例

### 完整工作流

```bash
# 1. 初始化
midlayer init

# 2. 添加项目文档
midlayer add README.md
midlayer add docs/
midlayer add src/

# 3. 查看统计
midlayer stats

# 4. 搜索测试
midlayer search "如何使用"
midlayer search "error handling" --verbose

# 5. 问答
export MIDLAYER_API_KEY="sk-xxx"
export MIDLAYER_LLM_MODEL="deepseek-chat"
export MIDLAYER_BASE_URL="https://api.deepseek.com/v1"

midlayer ask "这个项目解决什么问题？"

# 6. 交互对话
midlayer chat
```
