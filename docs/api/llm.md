# LLM 模块 API

> 大语言模型适配器，支持多种 LLM 提供商

## 概览

LLM 模块使用 LiteLLM 作为后端，支持：
- OpenAI (GPT-4, GPT-4o, GPT-3.5)
- Anthropic (Claude 3)
- Google (Gemini)
- DeepSeek
- 任何 OpenAI 兼容的 API

---

## LiteLLMClient

统一的 LLM 客户端。

### 初始化

```python
from ai_midlayer.llm import LiteLLMClient

# 使用 OpenAI
client = LiteLLMClient(
    model="gpt-4o-mini",
    api_key="sk-xxx",
)

# 使用 DeepSeek
client = LiteLLMClient(
    model="deepseek-chat",
    api_key="sk-xxx",
    base_url="https://api.deepseek.com/v1",
)

# 使用环境变量
import os
os.environ["OPENAI_API_KEY"] = "sk-xxx"
client = LiteLLMClient(model="gpt-4o-mini")
```

**参数:**
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `model` | `str` | `gpt-4o-mini` | 模型名称 |
| `api_key` | `str \| None` | `None` | API Key |
| `base_url` | `str \| None` | `None` | API 端点 |
| `temperature` | `float` | `0.7` | 生成温度 |
| `max_tokens` | `int` | `4096` | 最大 token 数 |

### 方法

#### generate

生成回复。

```python
response = client.generate(
    prompt="解释 Python 装饰器",
    system_prompt="你是一个 Python 专家",  # 可选
    temperature=0.5,  # 可选
    max_tokens=1000,  # 可选
)
print(response)
```

#### chat

多轮对话。

```python
from ai_midlayer.llm import Message

messages = [
    Message(role="user", content="什么是 RAG？"),
    Message(role="assistant", content="RAG 是检索增强生成..."),
    Message(role="user", content="详细说说检索部分"),
]

response = client.chat(messages)
print(response)
```

---

## LLMConfig

LLM 配置类。

```python
from ai_midlayer.llm import LLMConfig, LLMProvider

config = LLMConfig(
    provider=LLMProvider.OPENAI,
    model="gpt-4o-mini",
    api_key="sk-xxx",
    base_url=None,
    temperature=0.7,
    max_tokens=4096,
)

# 创建客户端
client = LiteLLMClient.from_config(config)
```

### LLMProvider 枚举

```python
from ai_midlayer.llm import LLMProvider

LLMProvider.OPENAI      # OpenAI
LLMProvider.ANTHROPIC   # Anthropic
LLMProvider.GOOGLE      # Google
LLMProvider.DEEPSEEK    # DeepSeek
LLMProvider.CUSTOM      # 自定义端点
```

---

## Message

对话消息。

```python
from ai_midlayer.llm import Message

message = Message(
    role="user",      # "user", "assistant", "system"
    content="Hello",
)
```

---

## 环境变量

| 变量 | 说明 |
|------|------|
| `MIDLAYER_API_KEY` | API Key |
| `MIDLAYER_BASE_URL` | API 端点 |
| `MIDLAYER_LLM_MODEL` | 模型名 |
| `MIDLAYER_LLM_PROVIDER` | 提供商 |
| `MIDLAYER_TEMPERATURE` | 温度 |
| `MIDLAYER_MAX_TOKENS` | 最大 token |

---

## 使用示例

### 基本使用

```python
from ai_midlayer.llm import LiteLLMClient

client = LiteLLMClient(
    model="deepseek-chat",
    api_key="your-key",
    base_url="https://api.deepseek.com/v1",
)

# 单次生成
response = client.generate("Python 是什么？")
print(response)
```

### 与 RAG 结合

```python
from ai_midlayer.llm import LiteLLMClient
from ai_midlayer.rag.query import RAGQueryEngine

llm = LiteLLMClient(model="gpt-4o-mini")
rag = RAGQueryEngine(retriever, llm)

answer = rag.query("项目如何工作？")
```

### 从配置文件加载

```python
from ai_midlayer.config import get_config

config = get_config()  # 从环境变量加载
llm = LiteLLMClient.from_config(config.llm)
```
