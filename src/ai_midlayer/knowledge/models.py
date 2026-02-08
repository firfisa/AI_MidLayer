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
    def from_file(cls, path: str | Path, ocr_client=None) -> "Document":
        """Create a Document from a file path.
        
        Supports:
        - Text files (.txt, .md, .py, etc.)
        - PDF files (with optional OCR for scanned documents)
        - Images (with OCR if client provided)
        
        Args:
            path: Path to file
            ocr_client: Optional OCRClient for image/scanned PDF support
        """
        path = Path(path)
        
        # 读取原始内容
        raw_content = path.read_bytes()
        file_type = path.suffix.lstrip(".").lower() or "unknown"
        
        # PDF 文件特殊处理
        if file_type == "pdf":
            content = cls._parse_pdf(path, ocr_client)
        # 图片文件 OCR
        elif file_type in ("jpg", "jpeg", "png", "gif", "webp", "bmp"):
            content = cls._parse_image(path, ocr_client)
        else:
            # 尝试解码为文本
            try:
                content = raw_content.decode("utf-8")
            except UnicodeDecodeError:
                content = ""  # 二进制文件，暂不解析
        
        return cls(
            source_path=str(path.absolute()),
            file_name=path.name,
            file_type=file_type,
            content=content,
            raw_content=raw_content,
            metadata={
                "size_bytes": len(raw_content),
                "is_binary": not content,
                "has_ocr": ocr_client is not None and file_type in ("pdf", "jpg", "jpeg", "png", "gif", "webp", "bmp"),
            }
        )
    
    @classmethod
    def _parse_pdf(cls, path: Path, ocr_client=None) -> str:
        """Parse PDF file content."""
        try:
            from ai_midlayer.knowledge.parsers.pdf import PDFParser
            parser = PDFParser(ocr_client=ocr_client)
            doc = parser.parse(path)
            return doc.content if doc else ""
        except ImportError:
            # Fallback: try basic pypdf
            try:
                import pypdf
                reader = pypdf.PdfReader(str(path))
                return "\n\n".join(page.extract_text() or "" for page in reader.pages)
            except Exception:
                return ""
        except Exception:
            return ""
    
    @classmethod
    def _parse_image(cls, path: Path, ocr_client=None) -> str:
        """Parse image file using OCR."""
        if ocr_client is None:
            return f"[Image: {path.name}]"
        
        try:
            return ocr_client.ocr_to_markdown(path)
        except Exception as e:
            return f"[Image OCR failed: {e}]"
    
    def __str__(self) -> str:
        return f"Document({self.file_name}, {len(self.chunks)} chunks)"


class SearchResult(BaseModel):
    """A search result from the knowledge base."""
    
    chunk: Chunk
    score: float
    doc: Document | None = None
    
    @property
    def file_name(self) -> str:
        """Get the file name from chunk metadata."""
        return self.chunk.metadata.get("file_name", "unknown")
    
    @property
    def content(self) -> str:
        """Get the chunk content."""
        return self.chunk.content
    
    def __str__(self) -> str:
        return f"SearchResult(score={self.score:.3f}): {self.chunk}"
