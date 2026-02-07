"""End-to-end tests for hybrid search functionality.

Tests the full pipeline: add files → hybrid search → compare results.
"""

import tempfile
import pytest
from pathlib import Path

from ai_midlayer.knowledge.store import FileStore
from ai_midlayer.knowledge.index import VectorIndex
from ai_midlayer.knowledge.bm25 import BM25Index
from ai_midlayer.knowledge.retriever import Retriever
from ai_midlayer.knowledge.models import Document


class TestHybridSearchE2E:
    """End-to-end tests for hybrid search."""
    
    @pytest.fixture
    def kb_with_docs(self):
        """Create a temporary knowledge base with test documents."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            kb_path = Path(tmp_dir) / ".midlayer"
            kb_path.mkdir(parents=True)
            docs_dir = Path(tmp_dir) / "docs"
            docs_dir.mkdir()
            
            # Create test document files
            doc_contents = {
                "python_guide.md": """Python Programming Guide
                    
Python is a high-level programming language known for its simplicity.
It supports multiple programming paradigms including procedural,
object-oriented, and functional programming. Python's syntax emphasizes
code readability and allows developers to express concepts in fewer
lines of code than possible in languages like C++ or Java.

Key features:
- Dynamic typing
- Garbage collection
- Extensive standard library
- Cross-platform compatibility""",
                
                "javascript_guide.md": """JavaScript Fundamentals
                    
JavaScript is a versatile language primarily used for web development.
It runs in browsers and can also be used for server-side development
with Node.js. JavaScript is dynamically typed and supports prototype-based
object orientation.

Key features:
- Event-driven programming
- First-class functions
- Asynchronous programming with Promises and async/await
- Used for both frontend and backend development""",
                
                "api_reference.md": """API Reference: reset_password()
                    
Function: reset_password(email: str) -> bool

Resets the password for a user account. Sends a password reset email
to the specified address.

Parameters:
- email: The email address of the user account

Returns:
- True if reset email was sent successfully
- False if email not found in system

Example:
    result = reset_password("user@example.com")
    if result:
        print("Check your email for reset instructions")""",
            }
            
            # Write files to disk
            for filename, content in doc_contents.items():
                (docs_dir / filename).write_text(content)
            
            # Initialize components
            store = FileStore(kb_path)
            vector_index = VectorIndex(kb_path)
            bm25_index = BM25Index(kb_path / "index" / "bm25.db")
            
            # Add files to store and index
            doc_ids = []
            for filename in doc_contents.keys():
                file_path = docs_dir / filename
                doc_id = store.add_file(file_path)
                doc = store.get_file(doc_id)
                if doc:
                    vector_index.index_document(doc)
                    bm25_index.index_document(doc)
                doc_ids.append(doc_id)
            
            yield {
                "kb_path": kb_path,
                "store": store,
                "vector_index": vector_index,
                "bm25_index": bm25_index,
                "doc_ids": doc_ids,
            }
    
    def test_hybrid_retriever_creation(self, kb_with_docs):
        """Test creating a hybrid retriever."""
        retriever = Retriever(
            store=kb_with_docs["store"],
            index=kb_with_docs["vector_index"],
            bm25_index=kb_with_docs["bm25_index"],
        )
        
        assert retriever.hybrid_enabled
        assert retriever.bm25_index is not None
    
    def test_hybrid_search_finds_relevant_docs(self, kb_with_docs):
        """Test that hybrid search finds relevant documents."""
        retriever = Retriever(
            store=kb_with_docs["store"],
            index=kb_with_docs["vector_index"],
            bm25_index=kb_with_docs["bm25_index"],
        )
        
        # Search for Python
        results = retriever.retrieve("Python programming language", top_k=3)
        
        assert len(results) > 0
        # Check that Python-related content is in top results
        top_content = " ".join(r.chunk.content.lower() for r in results[:2])
        assert "python" in top_content
    
    def test_exact_keyword_match_bm25_advantage(self, kb_with_docs):
        """Test that BM25 helps with exact keyword matches."""
        retriever = Retriever(
            store=kb_with_docs["store"],
            index=kb_with_docs["vector_index"],
            bm25_index=kb_with_docs["bm25_index"],
        )
        
        # Search for specific function name (BM25 should excel here)
        results = retriever.retrieve("reset_password", top_k=3)
        
        assert len(results) > 0
        # API doc should be in results (contains reset_password)
        assert "reset_password" in results[0].chunk.content
    
    def test_semantic_search_fallback(self, kb_with_docs):
        """Test semantic search when hybrid is disabled."""
        retriever = Retriever(
            store=kb_with_docs["store"],
            index=kb_with_docs["vector_index"],
            bm25_index=None,  # Disable BM25
        )
        
        assert not retriever.hybrid_enabled
        
        # Should still work with vector only
        results = retriever.retrieve("programming languages", top_k=3)
        assert len(results) > 0
    
    def test_hybrid_vs_vector_only_comparison(self, kb_with_docs):
        """Compare hybrid vs vector-only search results."""
        hybrid_retriever = Retriever(
            store=kb_with_docs["store"],
            index=kb_with_docs["vector_index"],
            bm25_index=kb_with_docs["bm25_index"],
        )
        
        vector_retriever = Retriever(
            store=kb_with_docs["store"],
            index=kb_with_docs["vector_index"],
            bm25_index=None,
        )
        
        # Exact term query where BM25 should help
        hybrid_results = hybrid_retriever.retrieve("async await promises", top_k=3)
        vector_results = vector_retriever.retrieve("async await promises", top_k=3)
        
        # Both should find results
        assert len(hybrid_results) > 0
        assert len(vector_results) > 0
        
        # Hybrid should have search_source metadata
        if hybrid_retriever.hybrid_enabled:
            for r in hybrid_results:
                # Should have some source metadata
                assert r.chunk.metadata is not None
    
    def test_force_hybrid_mode(self, kb_with_docs):
        """Test forcing hybrid mode on/off."""
        retriever = Retriever(
            store=kb_with_docs["store"],
            index=kb_with_docs["vector_index"],
            bm25_index=kb_with_docs["bm25_index"],
        )
        
        # Force hybrid off even though BM25 is available
        results_vector = retriever.retrieve("Python", top_k=3, use_hybrid=False)
        
        # Force hybrid on
        results_hybrid = retriever.retrieve("Python", top_k=3, use_hybrid=True)
        
        # Both should return results
        assert len(results_vector) > 0
        assert len(results_hybrid) > 0


class TestBM25IndexE2E:
    """End-to-end tests for BM25 indexing."""
    
    def test_chinese_content_indexing(self):
        """Test BM25 works with Chinese content."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "bm25.db"
            index = BM25Index(db_path)
            
            doc = Document(
                id="doc_chinese",
                content="""人工智能简介
                
人工智能（AI）是计算机科学的一个分支，致力于创建能够
执行通常需要人类智能的任务的系统。这些任务包括视觉感知、
语音识别、决策制定和语言翻译。

机器学习是人工智能的一个子领域，它使系统能够从数据中
学习和改进，而无需显式编程。深度学习是机器学习的一个子集，
使用神经网络来模拟人脑的工作方式。""",
                file_name="ai_intro.md",
                source_path="/docs/ai_intro.md",
                file_type="markdown",
            )
            
            chunks = index.index_document(doc)
            assert chunks > 0
            
            # Search for Chinese terms
            results = index.search("人工智能", top_k=5)
            assert len(results) > 0
            
            # Search for machine learning in Chinese
            results = index.search("机器学习", top_k=5)
            assert len(results) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
