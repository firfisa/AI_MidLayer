"""Tests for RAG query module."""

import pytest
from unittest.mock import Mock, MagicMock

from ai_midlayer.rag import RAGQuery, ConversationRAG, QueryResult
from ai_midlayer.knowledge.models import Chunk, SearchResult


class MockRetriever:
    """Mock Retriever for testing."""
    
    def __init__(self, results=None):
        self.results = results or []
    
    def retrieve(self, query: str, top_k: int = 5):
        return self.results[:top_k]


class MockLLMClient:
    """Mock LLM client for testing."""
    
    def __init__(self, response="Mock answer"):
        self.response = response
        self.calls = []
    
    def complete(self, messages, **kwargs):
        self.calls.append(messages)
        return Mock(content=self.response, usage={"total_tokens": 100})
    
    async def acomplete(self, messages, **kwargs):
        return self.complete(messages, **kwargs)


class TestQueryResult:
    """Tests for QueryResult."""
    
    def test_format_sources_empty(self):
        """Test formatting with no sources."""
        result = QueryResult(query="test", answer="answer")
        assert result.format_sources() == "无相关来源"
    
    def test_format_sources_with_results(self):
        """Test formatting with sources."""
        chunk = Chunk(
            doc_id="doc1",
            content="test content",
            start_idx=0,
            end_idx=12,
            metadata={"file_name": "test.md"}
        )
        result = QueryResult(
            query="test",
            answer="answer",
            sources=[SearchResult(chunk=chunk, score=0.9)]
        )
        formatted = result.format_sources()
        assert "test.md" in formatted
        assert "0.90" in formatted


class TestRAGQuery:
    """Tests for RAGQuery."""
    
    def test_query_empty_results(self):
        """Test query with no retrieval results."""
        retriever = MockRetriever([])
        llm = MockLLMClient("No documents found response")
        
        rag = RAGQuery(retriever, llm)
        result = rag.query("test question")
        
        assert result.answer == "No documents found response"
        assert len(result.sources) == 0
    
    def test_query_with_results(self):
        """Test query with retrieval results."""
        chunk = Chunk(
            doc_id="doc1",
            content="This is relevant content.",
            start_idx=0,
            end_idx=25,
            metadata={"file_name": "test.md"}
        )
        results = [SearchResult(chunk=chunk, score=0.85)]
        
        retriever = MockRetriever(results)
        llm = MockLLMClient("Based on the context, the answer is X.")
        
        rag = RAGQuery(retriever, llm)
        result = rag.query("what is X?")
        
        assert "answer is X" in result.answer
        assert len(result.sources) == 1
        assert result.sources[0].file_name == "test.md"
    
    def test_context_truncation(self):
        """Test context is truncated when too long."""
        long_content = "A" * 5000
        chunk = Chunk(
            doc_id="doc1",
            content=long_content,
            start_idx=0,
            end_idx=5000,
            metadata={"file_name": "long.txt"}
        )
        results = [SearchResult(chunk=chunk, score=0.9)]
        
        retriever = MockRetriever(results)
        llm = MockLLMClient("Truncated response")
        
        rag = RAGQuery(retriever, llm, max_context_length=1000)
        result = rag.query("test")
        
        # Context should be truncated
        assert len(result.context_used) <= 1100  # allow some buffer
    
    def test_custom_system_prompt(self):
        """Test with custom system prompt."""
        retriever = MockRetriever([])
        llm = MockLLMClient("Custom prompt response")
        
        custom_prompt = "Custom: {context}"
        rag = RAGQuery(retriever, llm, system_prompt=custom_prompt)
        result = rag.query("test")
        
        # LLM should receive messages with custom prompt
        assert len(llm.calls) == 1


class TestConversationRAG:
    """Tests for ConversationRAG."""
    
    def test_chat_history(self):
        """Test conversation history is maintained."""
        retriever = MockRetriever([])
        llm = MockLLMClient("Response")
        
        convo = ConversationRAG(retriever, llm)
        
        convo.chat("Question 1")
        convo.chat("Question 2")
        
        history = convo.get_history()
        assert len(history) == 2
        assert history[0][0] == "Question 1"
        assert history[1][0] == "Question 2"
    
    def test_clear_history(self):
        """Test clearing conversation history."""
        retriever = MockRetriever([])
        llm = MockLLMClient("Response")
        
        convo = ConversationRAG(retriever, llm)
        convo.chat("Question")
        assert len(convo.get_history()) == 1
        
        convo.clear_history()
        assert len(convo.get_history()) == 0
    
    def test_max_history_limit(self):
        """Test history is limited to max_history."""
        retriever = MockRetriever([])
        llm = MockLLMClient("Response")
        
        convo = ConversationRAG(retriever, llm, max_history=3)
        
        for i in range(5):
            convo.chat(f"Question {i}")
        
        history = convo.get_history()
        assert len(history) == 3
        assert history[0][0] == "Question 2"  # Oldest should be removed
