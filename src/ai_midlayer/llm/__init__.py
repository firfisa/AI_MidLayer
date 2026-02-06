"""LLM 适配器 - 支持多模型提供商和自定义 baseURL。

使用 LiteLLM 统一接口，支持:
- OpenAI (GPT-4, GPT-3.5)
- Anthropic (Claude)
- Google (Gemini)
- 本地模型 (Ollama, vLLM)
- 自定义 baseURL (OpenAI 兼容 API)

Architecture alignment: L1 Infrastructure Layer → LLM Provider
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ============================================================
# Configuration Models
# ============================================================

class LLMProvider(str, Enum):
    """支持的 LLM 提供商。"""
    
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    OLLAMA = "ollama"
    CUSTOM = "custom"  # OpenAI 兼容的自定义 API


class LLMConfig(BaseModel):
    """LLM 配置。"""
    
    provider: LLMProvider = LLMProvider.OPENAI
    model: str = "gpt-4o-mini"
    
    # API 配置
    api_key: str | None = None
    base_url: str | None = None  # 自定义 baseURL
    
    # 生成参数
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 1.0
    
    # 重试配置
    max_retries: int = 3
    timeout: int = 60
    
    # 额外参数
    extra_params: dict[str, Any] = Field(default_factory=dict)
    
    def get_model_string(self) -> str:
        """获取 LiteLLM 格式的模型字符串。
        
        LiteLLM 使用 provider/model 格式，例如:
        - openai/gpt-4
        - anthropic/claude-3-opus
        - ollama/llama3
        
        对于自定义 OpenAI 兼容 API (如 DeepSeek)，
        需要使用 openai/ 前缀 + base_url 参数。
        """
        if self.provider == LLMProvider.OPENAI:
            return self.model  # OpenAI 不需要前缀
        elif self.provider == LLMProvider.ANTHROPIC:
            return self.model  # Anthropic 不需要前缀
        elif self.provider == LLMProvider.GOOGLE:
            return f"gemini/{self.model}"
        elif self.provider == LLMProvider.OLLAMA:
            return f"ollama/{self.model}"
        elif self.provider == LLMProvider.CUSTOM:
            # 自定义 OpenAI 兼容 API 需要 openai/ 前缀
            return f"openai/{self.model}"
        else:
            return self.model


# ============================================================
# Message Models
# ============================================================

class MessageRole(str, Enum):
    """消息角色。"""
    
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class Message(BaseModel):
    """聊天消息。"""
    
    role: MessageRole
    content: str
    
    @classmethod
    def system(cls, content: str) -> "Message":
        """创建系统消息。"""
        return cls(role=MessageRole.SYSTEM, content=content)
    
    @classmethod
    def user(cls, content: str) -> "Message":
        """创建用户消息。"""
        return cls(role=MessageRole.USER, content=content)
    
    @classmethod
    def assistant(cls, content: str) -> "Message":
        """创建助手消息。"""
        return cls(role=MessageRole.ASSISTANT, content=content)
    
    def to_dict(self) -> dict:
        """转换为字典格式。"""
        return {"role": self.role.value, "content": self.content}


class CompletionResponse(BaseModel):
    """LLM 响应。"""
    
    content: str
    model: str = ""
    usage: dict[str, int] = Field(default_factory=dict)
    finish_reason: str = ""
    raw_response: Any = None


# ============================================================
# LLM Client Interface
# ============================================================

class BaseLLMClient(ABC):
    """LLM 客户端基类。"""
    
    @abstractmethod
    def complete(self, messages: list[Message], **kwargs) -> CompletionResponse:
        """同步调用 LLM。"""
        pass
    
    @abstractmethod
    async def acomplete(self, messages: list[Message], **kwargs) -> CompletionResponse:
        """异步调用 LLM。"""
        pass
    
    def chat(self, prompt: str, system: str | None = None, **kwargs) -> str:
        """简化的聊天接口。"""
        messages = []
        if system:
            messages.append(Message.system(system))
        messages.append(Message.user(prompt))
        
        response = self.complete(messages, **kwargs)
        return response.content


# ============================================================
# LiteLLM Client Implementation
# ============================================================

class LiteLLMClient(BaseLLMClient):
    """基于 LiteLLM 的客户端实现。
    
    支持:
    - OpenAI, Anthropic, Google, Ollama 等主流模型
    - 自定义 baseURL (OpenAI 兼容 API)
    - 统一的接口和错误处理
    
    Usage:
        # OpenAI
        client = LiteLLMClient(LLMConfig(
            provider=LLMProvider.OPENAI,
            model="gpt-4o-mini",
            api_key="sk-..."
        ))
        
        # 自定义 API (如 DeepSeek, 本地部署)
        client = LiteLLMClient(LLMConfig(
            provider=LLMProvider.CUSTOM,
            model="deepseek-chat",
            base_url="https://api.deepseek.com",
            api_key="..."
        ))
        
        # Ollama 本地模型
        client = LiteLLMClient(LLMConfig(
            provider=LLMProvider.OLLAMA,
            model="llama3",
            base_url="http://localhost:11434"
        ))
        
        response = client.chat("Hello, world!")
    """
    
    def __init__(self, config: LLMConfig):
        """初始化客户端。
        
        Args:
            config: LLM 配置
        """
        self.config = config
        self._setup_environment()
    
    def _setup_environment(self) -> None:
        """设置环境变量（如果提供了 API key）。"""
        import os
        
        if self.config.api_key:
            if self.config.provider == LLMProvider.OPENAI or self.config.provider == LLMProvider.CUSTOM:
                os.environ["OPENAI_API_KEY"] = self.config.api_key
            elif self.config.provider == LLMProvider.ANTHROPIC:
                os.environ["ANTHROPIC_API_KEY"] = self.config.api_key
            elif self.config.provider == LLMProvider.GOOGLE:
                os.environ["GEMINI_API_KEY"] = self.config.api_key
    
    def _get_completion_kwargs(self) -> dict:
        """获取 LiteLLM completion 参数。"""
        kwargs = {
            "model": self.config.get_model_string(),
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
            "top_p": self.config.top_p,
            "timeout": self.config.timeout,
            "num_retries": self.config.max_retries,
        }
        
        # 自定义 base_url
        if self.config.base_url:
            kwargs["base_url"] = self.config.base_url
            kwargs["api_key"] = self.config.api_key
        
        # 额外参数
        kwargs.update(self.config.extra_params)
        
        return kwargs
    
    def complete(self, messages: list[Message], **kwargs) -> CompletionResponse:
        """同步调用 LLM。"""
        import litellm
        
        # 准备参数
        completion_kwargs = self._get_completion_kwargs()
        completion_kwargs.update(kwargs)
        completion_kwargs["messages"] = [m.to_dict() for m in messages]
        
        try:
            response = litellm.completion(**completion_kwargs)
            
            return CompletionResponse(
                content=response.choices[0].message.content or "",
                model=response.model,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0,
                },
                finish_reason=response.choices[0].finish_reason or "",
                raw_response=response,
            )
            
        except Exception as e:
            # 简化错误处理，返回错误信息
            return CompletionResponse(
                content=f"Error: {str(e)}",
                finish_reason="error",
            )
    
    async def acomplete(self, messages: list[Message], **kwargs) -> CompletionResponse:
        """异步调用 LLM。"""
        import litellm
        
        # 准备参数
        completion_kwargs = self._get_completion_kwargs()
        completion_kwargs.update(kwargs)
        completion_kwargs["messages"] = [m.to_dict() for m in messages]
        
        try:
            response = await litellm.acompletion(**completion_kwargs)
            
            return CompletionResponse(
                content=response.choices[0].message.content or "",
                model=response.model,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0,
                },
                finish_reason=response.choices[0].finish_reason or "",
                raw_response=response,
            )
            
        except Exception as e:
            return CompletionResponse(
                content=f"Error: {str(e)}",
                finish_reason="error",
            )


# ============================================================
# Factory Function
# ============================================================

def create_llm_client(
    provider: str = "openai",
    model: str = "gpt-4o-mini",
    api_key: str | None = None,
    base_url: str | None = None,
    **kwargs
) -> LiteLLMClient:
    """创建 LLM 客户端的工厂函数。
    
    Args:
        provider: 提供商名称 (openai, anthropic, google, ollama, custom)
        model: 模型名称
        api_key: API 密钥
        base_url: 自定义 API 地址
        **kwargs: 其他配置参数
        
    Returns:
        配置好的 LiteLLMClient
        
    Examples:
        # OpenAI
        client = create_llm_client("openai", "gpt-4o-mini", api_key="sk-...")
        
        # Anthropic Claude
        client = create_llm_client("anthropic", "claude-3-opus-20240229", api_key="...")
        
        # DeepSeek (自定义 API)
        client = create_llm_client(
            "custom",
            "deepseek-chat",
            api_key="...",
            base_url="https://api.deepseek.com"
        )
        
        # Ollama 本地
        client = create_llm_client("ollama", "llama3", base_url="http://localhost:11434")
    """
    provider_enum = LLMProvider(provider.lower())
    
    config = LLMConfig(
        provider=provider_enum,
        model=model,
        api_key=api_key,
        base_url=base_url,
        **kwargs
    )
    
    return LiteLLMClient(config)


# ============================================================
# Convenience Functions
# ============================================================

def quick_chat(
    prompt: str,
    system: str | None = None,
    model: str = "gpt-4o-mini",
    api_key: str | None = None,
    base_url: str | None = None,
) -> str:
    """快速聊天函数。
    
    Args:
        prompt: 用户提示
        system: 系统提示
        model: 模型名称
        api_key: API 密钥
        base_url: 自定义 API 地址
        
    Returns:
        LLM 响应文本
    """
    client = create_llm_client(
        provider="custom" if base_url else "openai",
        model=model,
        api_key=api_key,
        base_url=base_url,
    )
    return client.chat(prompt, system=system)
