"""Tests for LLM Reranker and Query Expansion modules."""

import pytest
from unittest.mock import Mock, MagicMock

from ai_midlayer.knowledge.models import Chunk, SearchResult
from ai_midlayer.rag.reranker import (
    LLMReranker,
    NoOpReranker,
    ScoreBasedReranker,
    RerankResult,
)
from ai_midlayer.rag.expansion import (
    LLMQueryExpander,
    SimpleQueryExpander,
    NoOpExpander,
    ExpandedQuery,
)


# Helper function
def make_result(doc_id: str, score: float, content: str = "test content") -> SearchResult:
    """Create a test SearchResult."""
    chunk = Chunk(
        id=f"chunk_{doc_id}",
        doc_id=doc_id,
        content=content,
        start_idx=0,
        end_idx=len(content),
        metadata={"file_name": f"{doc_id}.md"}
    )
    return SearchResult(chunk=chunk, score=score)


class TestNoOpReranker:
    """NoOpReranker tests."""
    
    def test_returns_original_order(self):
        """Test that NoOpReranker preserves order."""
        results = [
            make_result("doc1", 0.9),
            make_result("doc2", 0.8),
            make_result("doc3", 0.7),
        ]
        
        reranker = NoOpReranker()
        reranked = reranker.rerank("test query", results)
        
        assert len(reranked) == 3
        assert reranked[0].chunk.doc_id == "doc1"
        assert reranked[1].chunk.doc_id == "doc2"
    
    def test_respects_top_k(self):
        """Test top_k limit."""
        results = [make_result(f"doc{i}", 0.9 - i*0.1) for i in range(10)]
        
        reranker = NoOpReranker()
        reranked = reranker.rerank("query", results, top_k=5)
        
        assert len(reranked) == 5


class TestScoreBasedReranker:
    """ScoreBasedReranker tests."""
    
    def test_keyword_density_boost(self):
        """Test that documents with more query terms get boosted."""
        results = [
            make_result("doc1", 0.5, "unrelated content here"),
            make_result("doc2", 0.5, "python programming is fun python code"),
        ]
        
        reranker = ScoreBasedReranker()
        reranked = reranker.rerank("python programming", results)
        
        # doc2 has more query terms, should be ranked higher
        assert reranked[0].chunk.doc_id == "doc2"
    
    def test_length_penalty(self):
        """Test that very short documents get penalized."""
        results = [
            make_result("doc1", 0.7, "short"),  # Very short
            make_result("doc2", 0.7, "This is a longer document with more content " * 5),
        ]
        
        reranker = ScoreBasedReranker()
        reranked = reranker.rerank("test", results)
        
        # doc2 should be ranked higher (less penalty)
        assert reranked[0].chunk.doc_id == "doc2"


class TestLLMReranker:
    """LLMReranker tests with mocked LLM."""
    
    def test_rerank_with_mock_llm(self):
        """Test reranking with mocked LLM responses."""
        mock_llm = Mock()
        # Return decreasing scores
        mock_llm.chat.side_effect = ["0.9", "0.7", "0.8"]
        
        results = [
            make_result("doc1", 0.5),
            make_result("doc2", 0.5),
            make_result("doc3", 0.5),
        ]
        
        reranker = LLMReranker(mock_llm, use_position_blend=False)
        reranked = reranker.rerank("query", results, top_k=3)
        
        assert len(reranked) == 3
        # LLM scores: doc1=0.9, doc2=0.7, doc3=0.8
        # Simple 50/50 blend: doc1 should be first
        assert reranked[0].chunk.doc_id == "doc1"
    
    def test_parse_score_various_formats(self):
        """Test score parsing handles various formats."""
        mock_llm = Mock()
        reranker = LLMReranker(mock_llm)
        
        # Test various response formats
        assert reranker._parse_score("0.85") == 0.85
        assert reranker._parse_score("0.9\n") == 0.9
        assert reranker._parse_score("Score: 0.75") == 0.75
        assert reranker._parse_score("The relevance is 0.6") == 0.6
        
        # Edge cases
        assert reranker._parse_score("1.5") == 1.0  # Capped
        assert reranker._parse_score("invalid") == 0.5  # Default
    
    def test_llm_failure_graceful(self):
        """Test graceful handling of LLM failures."""
        mock_llm = Mock()
        mock_llm.chat.side_effect = Exception("API Error")
        
        results = [make_result("doc1", 0.8)]
        
        reranker = LLMReranker(mock_llm)
        reranked = reranker.rerank("query", results)
        
        # Should return result even on failure (score modified by position blend)
        assert len(reranked) == 1
        # Score should be > 0 (graceful fallback)
        assert reranked[0].score > 0


class TestNoOpExpander:
    """NoOpExpander tests."""
    
    def test_returns_original(self):
        """Test that NoOpExpander returns only original query."""
        expander = NoOpExpander()
        expanded = expander.expand("test query")
        
        assert expanded.original == "test query"
        assert expanded.lex_variants == []
        assert expanded.vec_variants == []
        assert expanded.hyde_doc is None


class TestSimpleQueryExpander:
    """SimpleQueryExpander tests."""
    
    def test_synonym_expansion(self):
        """Test synonym-based expansion."""
        expander = SimpleQueryExpander()
        expanded = expander.expand("create new file")
        
        assert expanded.original == "create new file"
        # Should have at least one variant with synonym
        assert len(expanded.lex_variants) > 0
        # Check for expected synonyms
        variants_str = ' '.join(expanded.lex_variants)
        assert 'make' in variants_str or 'build' in variants_str or 'generate' in variants_str
    
    def test_question_mark_removal(self):
        """Test question mark removal."""
        expander = SimpleQueryExpander()
        expanded = expander.expand("how do i create file?")
        
        # Should have variant without question mark
        assert any('?' not in v for v in expanded.lex_variants)
    
    def test_prefix_removal(self):
        """Test removal of common prefixes."""
        expander = SimpleQueryExpander()
        expanded = expander.expand("how to reset password")
        
        # Should have variant without "how to"
        assert any("reset password" in v for v in expanded.lex_variants)


class TestLLMQueryExpander:
    """LLMQueryExpander tests with mocked LLM."""
    
    def test_parse_expansion_response(self):
        """Test parsing of LLM expansion response."""
        mock_llm = Mock()
        mock_llm.chat.return_value = """lex: password reset; forgot password; recover account
vec: How do I reset my account password?; Steps to recover lost password
hyde: To reset your password, go to the login page and click Forgot Password. Enter your email to receive a reset link."""
        
        expander = LLMQueryExpander(mock_llm)
        expanded = expander.expand("reset password")
        
        assert expanded.original == "reset password"
        assert len(expanded.lex_variants) > 0
        assert "password reset" in expanded.lex_variants
        assert len(expanded.vec_variants) > 0
        assert expanded.hyde_doc is not None
        assert "reset" in expanded.hyde_doc.lower()
    
    def test_llm_failure_graceful(self):
        """Test graceful handling of LLM failures."""
        mock_llm = Mock()
        mock_llm.chat.side_effect = Exception("API Error")
        
        expander = LLMQueryExpander(mock_llm)
        expanded = expander.expand("test query")
        
        # Should return original query on failure
        assert expanded.original == "test query"
        assert expanded.lex_variants == []


class TestExpandedQuery:
    """ExpandedQuery dataclass tests."""
    
    def test_get_all_queries(self):
        """Test getting all query variants."""
        expanded = ExpandedQuery(
            original="test",
            lex_variants=["lex1", "lex2"],
            vec_variants=["vec1"],
            hyde_doc=None
        )
        
        all_queries = expanded.get_all_queries()
        assert len(all_queries) == 4
        assert "test" in all_queries
        assert "lex1" in all_queries
        assert "vec1" in all_queries
    
    def test_get_bm25_queries(self):
        """Test getting BM25-specific queries."""
        expanded = ExpandedQuery(
            original="test",
            lex_variants=["lex1"],
            vec_variants=["vec1"],
        )
        
        bm25_queries = expanded.get_bm25_queries()
        assert len(bm25_queries) == 2
        assert "test" in bm25_queries
        assert "lex1" in bm25_queries
        assert "vec1" not in bm25_queries
    
    def test_get_vector_queries_with_hyde(self):
        """Test getting vector queries including HyDE doc."""
        expanded = ExpandedQuery(
            original="test",
            lex_variants=["lex1"],
            vec_variants=["vec1"],
            hyde_doc="This is a hypothetical document."
        )
        
        vec_queries = expanded.get_vector_queries()
        assert len(vec_queries) == 3
        assert "test" in vec_queries
        assert "vec1" in vec_queries
        assert "This is a hypothetical document." in vec_queries


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
