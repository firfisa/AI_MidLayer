"""Data models for knowledge management."""

from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class Chunk(BaseModel):
    """A chunk of content from a document."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    content: str
    doc_id: str
    start_idx: int
    end_idx: int
    metadata: dict[str, Any] = Field(default_factory=dict)
    
    def __str__(self) -> str:
        preview = self.content[:100] + "..." if len(self.content) > 100 else self.content
        return f"Chunk({self.id[:8]}): {preview}"


class Document(BaseModel):
    """A document in the knowledge base."""
    
    id: str = Field(default_factory=lambda: str(uuid4()))
    source_path: str
    file_name: str
    file_type: str
    content: str
    raw_content: bytes | None = None  # 原始二进制内容（无损存储）
    chunks: list[Chunk] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    @classmethod
    def from_file(cls, path: str | Path) -> "Document":
        """Create a Document from a file path."""
        path = Path(path)
        
        # 读取原始内容
        raw_content = path.read_bytes()
        
        # 尝试解码为文本
        try:
            content = raw_content.decode("utf-8")
        except UnicodeDecodeError:
            content = ""  # 二进制文件，暂不解析
        
        return cls(
            source_path=str(path.absolute()),
            file_name=path.name,
            file_type=path.suffix.lstrip(".").lower() or "unknown",
            content=content,
            raw_content=raw_content,
            metadata={
                "size_bytes": len(raw_content),
                "is_binary": not content,
            }
        )
    
    def __str__(self) -> str:
        return f"Document({self.file_name}, {len(self.chunks)} chunks)"


class SearchResult(BaseModel):
    """A search result from the knowledge base."""
    
    chunk: Chunk
    score: float
    doc: Document | None = None
    
    def __str__(self) -> str:
        return f"SearchResult(score={self.score:.3f}): {self.chunk}"
