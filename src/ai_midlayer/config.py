"""配置管理模块。

支持:
- 环境变量配置
- 配置文件 (YAML/JSON)
- 命令行参数覆盖
"""

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from ai_midlayer.llm import LLMConfig, LLMProvider


class EmbeddingConfig(BaseModel):
    """嵌入模型配置。"""
    
    model: str = "all-MiniLM-L6-v2"  # 默认本地模型
    api_key: str | None = None
    base_url: str | None = None  # 自定义 API 端点
    dimensions: int = 1536  # 嵌入维度
    
    @property
    def use_api(self) -> bool:
        """是否使用 API 模型。"""
        return self.api_key is not None and self.base_url is not None


class KnowledgeBaseConfig(BaseModel):
    """知识库配置。"""
    
    path: str = ".midlayer"
    chunk_size: int = 500
    chunk_overlap: int = 100
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)


class AgentConfig(BaseModel):
    """Agent 配置。"""
    
    max_iterations: int = 3
    enable_reflexion: bool = True


class Config(BaseModel):
    """全局配置。"""
    
    # LLM 配置
    llm: LLMConfig = Field(default_factory=LLMConfig)
    
    # 知识库配置
    knowledge_base: KnowledgeBaseConfig = Field(default_factory=KnowledgeBaseConfig)
    
    # Agent 配置
    agent: AgentConfig = Field(default_factory=AgentConfig)
    
    # 日志级别
    log_level: str = "INFO"
    
    @classmethod
    def from_env(cls) -> "Config":
        """从环境变量创建配置。"""
        llm_config = LLMConfig(
            provider=LLMProvider(os.getenv("MIDLAYER_LLM_PROVIDER", "openai")),
            model=os.getenv("MIDLAYER_LLM_MODEL", "gpt-4o-mini"),
            api_key=os.getenv("MIDLAYER_API_KEY") or os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("MIDLAYER_BASE_URL"),
            temperature=float(os.getenv("MIDLAYER_TEMPERATURE", "0.7")),
            max_tokens=int(os.getenv("MIDLAYER_MAX_TOKENS", "4096")),
        )
        
        # 嵌入模型配置
        embedding_config = EmbeddingConfig(
            model=os.getenv("MIDLAYER_EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
            api_key=os.getenv("MIDLAYER_EMBEDDING_API_KEY"),
            base_url=os.getenv("MIDLAYER_EMBEDDING_BASE_URL"),
            dimensions=int(os.getenv("MIDLAYER_EMBEDDING_DIMENSIONS", "1536")),
        )
        
        return cls(
            llm=llm_config,
            knowledge_base=KnowledgeBaseConfig(
                path=os.getenv("MIDLAYER_KB_PATH", ".midlayer"),
                embedding=embedding_config,
            ),
            log_level=os.getenv("MIDLAYER_LOG_LEVEL", "INFO"),
        )
    
    @classmethod
    def from_file(cls, path: str | Path) -> "Config":
        """从配置文件加载。"""
        import json
        
        path = Path(path)
        if not path.exists():
            return cls()
        
        content = path.read_text()
        
        if path.suffix in [".yaml", ".yml"]:
            try:
                import yaml
                data = yaml.safe_load(content)
            except ImportError:
                raise ImportError("PyYAML is required for YAML config files")
        else:
            data = json.loads(content)
        
        return cls.model_validate(data)
    
    def save(self, path: str | Path) -> None:
        """保存配置到文件。"""
        import json
        
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        path.write_text(json.dumps(self.model_dump(), indent=2, default=str))


# 全局配置实例
_config: Config | None = None


def get_config() -> Config:
    """获取全局配置。"""
    global _config
    if _config is None:
        _config = Config.from_env()
    return _config


def set_config(config: Config) -> None:
    """设置全局配置。"""
    global _config
    _config = config
