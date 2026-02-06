"""Tests for VectorIndex and Retriever."""

import tempfile
from pathlib import Path

import pytest

from ai_midlayer.knowledge.models import Document
from ai_midlayer.knowledge.store import FileStore
from ai_midlayer.knowledge.index import VectorIndex
from ai_midlayer.knowledge.retriever import Retriever


class TestVectorIndex:
    """Tests for VectorIndex."""
    
    def test_chunk_text(self, tmp_path):
        """Test text chunking."""
        index = VectorIndex(tmp_path / "kb")
        
        text = "This is sentence one. This is sentence two. This is sentence three."
        chunks = index._chunk_text(text, "test-doc")
        
        assert len(chunks) >= 1
        assert all(c.doc_id == "test-doc" for c in chunks)
    
    def test_index_document(self, tmp_path):
        """Test indexing a document."""
        index = VectorIndex(tmp_path / "kb")
        
        doc = Document(
            id="doc-123",
            source_path="/test/file.md",
            file_name="file.md",
            file_type="md",
            content="# Test Document\n\nThis is a test document with some content. " * 10
        )
        
        num_chunks = index.index_document(doc)
        assert num_chunks > 0
        assert len(doc.chunks) == num_chunks
    
    def test_search(self, tmp_path):
        """Test searching indexed documents."""
        index = VectorIndex(tmp_path / "kb")
        
        # Index a document
        doc = Document(
            id="doc-456",
            source_path="/test/file.md",
            file_name="file.md",
            file_type="md",
            content="Python is a programming language. It is used for machine learning and AI development."
        )
        index.index_document(doc)
        
        # Search
        results = index.search("programming language", top_k=3)
        
        assert len(results) > 0
        assert results[0].chunk.doc_id == "doc-456"
    
    def test_remove_document(self, tmp_path):
        """Test removing a document from index."""
        index = VectorIndex(tmp_path / "kb")
        
        doc = Document(
            id="doc-789",
            source_path="/test/file.md",
            file_name="file.md",
            file_type="md",
            content="Content to be removed. " * 20
        )
        index.index_document(doc)
        
        # Verify indexed
        stats_before = index.get_stats()
        assert stats_before["total_chunks"] > 0
        
        # Remove
        removed = index.remove_document("doc-789")
        assert removed > 0
    
    def test_get_stats(self, tmp_path):
        """Test getting index statistics."""
        index = VectorIndex(tmp_path / "kb")
        
        # Empty index
        stats = index.get_stats()
        assert stats["total_chunks"] == 0
        assert stats["total_documents"] == 0
        
        # After indexing
        doc = Document(
            id="doc-stats",
            source_path="/test/file.md",
            file_name="file.md",
            file_type="md",
            content="Test content for statistics. " * 10
        )
        index.index_document(doc)
        
        stats = index.get_stats()
        assert stats["total_chunks"] > 0
        assert stats["total_documents"] == 1


class TestRetriever:
    """Tests for Retriever."""
    
    def test_retrieve(self, tmp_path):
        """Test basic retrieval."""
        kb_path = tmp_path / "kb"
        store = FileStore(kb_path)
        index = VectorIndex(kb_path)
        retriever = Retriever(store, index)
        
        # Create a test file
        test_file = tmp_path / "test.md"
        test_file.write_text("# Machine Learning\n\nMachine learning is a subset of AI.")
        
        # Add to store and index
        doc_id = store.add_file(test_file)
        doc = store.get_file(doc_id)
        index.index_document(doc)
        
        # Retrieve
        results = retriever.retrieve("machine learning", top_k=3)
        
        assert len(results) > 0
    
    def test_get_full_document(self, tmp_path):
        """Test getting full document."""
        kb_path = tmp_path / "kb"
        store = FileStore(kb_path)
        index = VectorIndex(kb_path)
        retriever = Retriever(store, index)
        
        # Create a test file
        test_file = tmp_path / "full.md"
        test_file.write_text("Full document content here.")
        
        doc_id = store.add_file(test_file)
        
        # Get full document
        doc = retriever.get_full_document(doc_id)
        
        assert doc is not None
        assert "Full document content" in doc.content
    
    def test_empty_retrieval(self, tmp_path):
        """Test retrieval from empty index."""
        kb_path = tmp_path / "kb"
        store = FileStore(kb_path)
        index = VectorIndex(kb_path)
        retriever = Retriever(store, index)
        
        results = retriever.retrieve("anything", top_k=5)
        
        assert len(results) == 0
