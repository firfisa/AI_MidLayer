"""Tests for knowledge module."""

import tempfile
from pathlib import Path

import pytest

from ai_midlayer.knowledge.models import Document, Chunk
from ai_midlayer.knowledge.store import FileStore


class TestDocument:
    """Tests for Document model."""
    
    def test_from_file_text(self, tmp_path):
        """Test creating Document from text file."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test\n\nHello world!")
        
        doc = Document.from_file(test_file)
        
        assert doc.file_name == "test.md"
        assert doc.file_type == "md"
        assert "Hello world" in doc.content
        assert doc.raw_content is not None
    
    def test_from_file_missing(self):
        """Test creating Document from missing file."""
        with pytest.raises(FileNotFoundError):
            Document.from_file("/nonexistent/file.txt")


class TestFileStore:
    """Tests for FileStore."""
    
    def test_add_and_get_file(self, tmp_path):
        """Test adding and retrieving a file."""
        # Create a test file
        test_file = tmp_path / "docs" / "test.md"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("# Test Document\n\nSome content here.")
        
        # Create store in separate directory
        kb_path = tmp_path / "kb"
        store = FileStore(kb_path)
        
        # Add file
        doc_id = store.add_file(test_file)
        assert doc_id is not None
        
        # Get file
        doc = store.get_file(doc_id)
        assert doc is not None
        assert doc.file_name == "test.md"
        assert "Test Document" in doc.content
    
    def test_list_files(self, tmp_path):
        """Test listing files."""
        # Create test files
        (tmp_path / "a.txt").write_text("File A")
        (tmp_path / "b.txt").write_text("File B")
        
        kb_path = tmp_path / "kb"
        store = FileStore(kb_path)
        
        store.add_file(tmp_path / "a.txt")
        store.add_file(tmp_path / "b.txt")
        
        files = store.list_files()
        assert len(files) == 2
    
    def test_remove_file(self, tmp_path):
        """Test removing a file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Test content")
        
        kb_path = tmp_path / "kb"
        store = FileStore(kb_path)
        
        doc_id = store.add_file(test_file)
        assert store.remove_file(doc_id) is True
        assert store.get_file(doc_id) is None
        assert len(store.list_files()) == 0
    
    def test_remove_nonexistent(self, tmp_path):
        """Test removing nonexistent file."""
        store = FileStore(tmp_path / "kb")
        assert store.remove_file("nonexistent-id") is False
