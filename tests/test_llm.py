"""Tests for LLM integration."""

import os
import pytest

from ai_midlayer.llm import (
    LLMConfig,
    LLMProvider,
    LiteLLMClient,
    Message,
    MessageRole,
    CompletionResponse,
    create_llm_client,
)
from ai_midlayer.config import Config, get_config
from ai_midlayer.agents.llm_agent import LLMAgentMixin


class TestLLMConfig:
    """Tests for LLMConfig."""
    
    def test_default_config(self):
        """Test default configuration."""
        config = LLMConfig()
        
        assert config.provider == LLMProvider.OPENAI
        assert config.model == "gpt-4o-mini"
        assert config.temperature == 0.7
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = LLMConfig(
            provider=LLMProvider.CUSTOM,
            model="deepseek-chat",
            base_url="https://api.deepseek.com",
            api_key="test-key",
            temperature=0.5,
        )
        
        assert config.provider == LLMProvider.CUSTOM
        assert config.base_url == "https://api.deepseek.com"
        assert config.temperature == 0.5
    
    def test_ollama_config(self):
        """Test Ollama configuration."""
        config = LLMConfig(
            provider=LLMProvider.OLLAMA,
            model="llama3",
            base_url="http://localhost:11434",
        )
        
        assert config.get_model_string() == "ollama/llama3"


class TestMessage:
    """Tests for Message model."""
    
    def test_create_messages(self):
        """Test creating different message types."""
        system = Message.system("You are a helpful assistant.")
        user = Message.user("Hello!")
        assistant = Message.assistant("Hi there!")
        
        assert system.role == MessageRole.SYSTEM
        assert user.role == MessageRole.USER
        assert assistant.role == MessageRole.ASSISTANT
    
    def test_to_dict(self):
        """Test message to dict conversion."""
        msg = Message.user("Hello!")
        d = msg.to_dict()
        
        assert d == {"role": "user", "content": "Hello!"}


class TestLiteLLMClient:
    """Tests for LiteLLMClient."""
    
    def test_client_creation(self):
        """Test client creation without API key."""
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            model="gpt-4o-mini",
        )
        client = LiteLLMClient(config)
        
        assert client.config.model == "gpt-4o-mini"
    
    def test_create_llm_client_factory(self):
        """Test factory function."""
        client = create_llm_client(
            provider="custom",
            model="test-model",
            base_url="http://localhost:8000",
            api_key="test-key",
        )
        
        assert client.config.provider == LLMProvider.CUSTOM
        assert client.config.base_url == "http://localhost:8000"


class TestConfig:
    """Tests for Config module."""
    
    def test_default_config(self):
        """Test default configuration."""
        config = Config()
        
        assert config.llm.provider == LLMProvider.OPENAI
        assert config.knowledge_base.path == ".midlayer"
        assert config.agent.max_iterations == 3
    
    def test_config_from_env(self, monkeypatch):
        """Test configuration from environment variables."""
        monkeypatch.setenv("MIDLAYER_LLM_PROVIDER", "anthropic")
        monkeypatch.setenv("MIDLAYER_LLM_MODEL", "claude-3-opus")
        monkeypatch.setenv("MIDLAYER_API_KEY", "test-key")
        monkeypatch.setenv("MIDLAYER_KB_PATH", "/custom/path")
        
        config = Config.from_env()
        
        assert config.llm.provider == LLMProvider.ANTHROPIC
        assert config.llm.model == "claude-3-opus"
        assert config.llm.api_key == "test-key"
        assert config.knowledge_base.path == "/custom/path"


class TestLLMAgentMixin:
    """Tests for LLMAgentMixin."""
    
    def test_mixin_without_llm(self):
        """Test mixin works without LLM configured."""
        mixin = LLMAgentMixin()
        
        assert mixin.llm_client is None
        assert not mixin.has_llm()
    
    def test_mixin_with_llm_config(self):
        """Test mixin with LLM config."""
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            model="gpt-4o-mini",
            api_key="test-key",
        )
        mixin = LLMAgentMixin(llm_config=config)
        
        assert mixin.has_llm()
        assert mixin.llm_client is not None
    
    def test_mixin_system_prompt(self):
        """Test mixin system prompt."""
        mixin = LLMAgentMixin(system_prompt="Custom prompt")
        
        assert mixin.system_prompt == "Custom prompt"
    
    def test_call_llm_without_client(self):
        """Test _call_llm returns empty string without client."""
        mixin = LLMAgentMixin()
        
        result = mixin._call_llm("test prompt")
        
        assert result == ""


# ============================================================
# Integration Tests (require API key)
# ============================================================

@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set"
)
class TestLLMIntegration:
    """Integration tests that require an API key."""
    
    def test_simple_completion(self):
        """Test simple LLM completion."""
        client = create_llm_client(
            provider="openai",
            model="gpt-4o-mini",
        )
        
        response = client.chat("Say 'hello' and nothing else.")
        
        assert "hello" in response.lower()
    
    def test_llm_mixin_orient(self):
        """Test LLMAgentMixin orient with LLM."""
        from ai_midlayer.agents.protocols import AgentState
        
        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            model="gpt-4o-mini",
        )
        mixin = LLMAgentMixin(llm_config=config)
        state = AgentState(input="Analyze this document")
        
        observation = {"file_type": "markdown", "content_length": 1000}
        analysis = mixin.orient_with_llm(state, observation)
        
        assert len(analysis) > 0
