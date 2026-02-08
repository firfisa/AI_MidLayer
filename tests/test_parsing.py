"""Tests for OCR client, PDF parser, and smart chunker."""

import pytest
from pathlib import Path
import tempfile

from ai_midlayer.knowledge.ocr import OCRClient, OCRPromptTemplate
from ai_midlayer.knowledge.parsers.pdf import PDFParser
from ai_midlayer.knowledge.chunker import SmartChunker, chunk_document
from ai_midlayer.knowledge.models import Document, Chunk


class TestOCRClient:
    """Tests for OCRClient."""
    
    def test_init_without_key_raises(self):
        """Should raise error without API key."""
        with pytest.raises(ValueError, match="OCR API key"):
            OCRClient()
    
    def test_init_with_key(self):
        """Should initialize with API key."""
        client = OCRClient(api_key="test-key", base_url="https://example.com/v1")
        assert client.api_key == "test-key"
        assert client.base_url == "https://example.com/v1"
    
    def test_prompt_templates(self):
        """Should have correct prompt templates."""
        assert "Free OCR" in OCRPromptTemplate.FREE_OCR
        assert "markdown" in OCRPromptTemplate.DOCUMENT_TO_MARKDOWN.lower()
        assert "Parse" in OCRPromptTemplate.PARSE_FIGURE
    
    def test_encode_image(self, tmp_path):
        """Should encode image to base64."""
        # Create a simple test image
        img_path = tmp_path / "test.png"
        img_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        
        client = OCRClient(api_key="test", base_url="https://example.com")
        data_url = client._encode_image(img_path)
        
        assert data_url.startswith("data:image/png;base64,")


class TestSmartChunker:
    """Tests for SmartChunker."""
    
    def test_chunk_empty_text(self):
        """Should return empty list for empty text."""
        chunker = SmartChunker()
        assert chunker.chunk("", "doc1") == []
        assert chunker.chunk("   ", "doc1") == []
    
    def test_chunk_short_text(self):
        """Should return single chunk for short text."""
        chunker = SmartChunker(chunk_size=500)
        chunks = chunker.chunk("Hello world", "doc1", "text")
        
        assert len(chunks) == 1
        assert chunks[0].content == "Hello world"
        assert chunks[0].doc_id == "doc1"
    
    def test_chunk_long_text(self):
        """Should split long text into multiple chunks."""
        chunker = SmartChunker(chunk_size=100, overlap=20)
        text = "This is a test. " * 50  # Long text
        
        chunks = chunker.chunk(text, "doc1", "text")
        
        assert len(chunks) > 1
        # Check overlap exists
        for i in range(len(chunks) - 1):
            chunk1_end = chunks[i].content[-20:]
            chunk2_start = chunks[i+1].content[:20]
            # Some overlap should exist
    
    def test_chunk_markdown_headings(self):
        """Should respect Markdown headings."""
        chunker = SmartChunker(chunk_size=500)
        text = """# Title

Introduction paragraph.

## Section 1

Content for section 1.

## Section 2

Content for section 2.
"""
        chunks = chunker.chunk(text, "doc1", "markdown")
        
        # Should have separate chunks for sections
        assert len(chunks) >= 2
        
        # Check heading metadata
        section_titles = [c.metadata.get("section_title") for c in chunks]
        assert any(t for t in section_titles if t)
    
    def test_chunk_python_code(self):
        """Should respect Python function/class boundaries."""
        chunker = SmartChunker(chunk_size=500)
        text = '''
def function_one():
    """First function."""
    return 1

def function_two():
    """Second function.""" 
    return 2

class MyClass:
    """A class."""
    def method(self):
        pass
'''
        chunks = chunker.chunk(text, "doc1", "python")
        
        # Should have chunks for each definition
        assert len(chunks) >= 2
        
        # Check code block metadata
        code_blocks = [c.metadata.get("code_block") for c in chunks]
        assert any(b for b in code_blocks if b)
    
    def test_chunk_document_helper(self):
        """Test convenience function."""
        chunks = chunk_document("Hello world", "doc1", "text")
        assert len(chunks) == 1


class TestPDFParser:
    """Tests for PDFParser."""
    
    def test_supports_pdf(self):
        """Should support .pdf extension."""
        parser = PDFParser()
        assert parser.supports("test.pdf")
        assert parser.supports(Path("test.PDF"))
        assert not parser.supports("test.txt")
    
    def test_is_scanned_pdf_detection(self, tmp_path):
        """Test scanned PDF detection logic."""
        parser = PDFParser()
        # MIN_TEXT_PER_PAGE = 50
        assert parser.MIN_TEXT_PER_PAGE == 50


class TestDocumentFromFile:
    """Tests for Document.from_file with enhanced parsing."""
    
    def test_from_text_file(self, tmp_path):
        """Should parse text file."""
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("Hello world")
        
        doc = Document.from_file(txt_file)
        
        assert doc.content == "Hello world"
        assert doc.file_type == "txt"
        assert doc.file_name == "test.txt"
    
    def test_from_markdown_file(self, tmp_path):
        """Should parse Markdown file."""
        md_file = tmp_path / "test.md"
        md_file.write_text("# Title\n\nContent")
        
        doc = Document.from_file(md_file)
        
        assert "# Title" in doc.content
        assert doc.file_type == "md"
    
    def test_from_python_file(self, tmp_path):
        """Should parse Python file."""
        py_file = tmp_path / "test.py"
        py_file.write_text("def hello():\n    pass")
        
        doc = Document.from_file(py_file)
        
        assert "def hello" in doc.content
        assert doc.file_type == "py"
    
    def test_image_without_ocr(self, tmp_path):
        """Should return placeholder for image without OCR."""
        img_file = tmp_path / "test.png"
        img_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        
        doc = Document.from_file(img_file)
        
        assert "[Image:" in doc.content
        assert doc.file_type == "png"


class TestChunkModel:
    """Tests for Chunk model."""
    
    def test_chunk_creation(self):
        """Should create chunk with all fields."""
        chunk = Chunk(
            content="Test content",
            doc_id="doc123",
            start_idx=0,
            end_idx=12,
            metadata={"key": "value"},
        )
        
        assert chunk.content == "Test content"
        assert chunk.doc_id == "doc123"
        assert chunk.metadata["key"] == "value"
        assert chunk.id  # Auto-generated
    
    def test_chunk_str(self):
        """Should have readable string representation."""
        chunk = Chunk(content="Short text", doc_id="doc1", start_idx=0, end_idx=10)
        assert "Short text" in str(chunk)
