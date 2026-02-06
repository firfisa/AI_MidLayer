"""Retriever for RAG search - combines FileStore and VectorIndex.

Implements hybrid retrieval from the system architecture:
- Semantic search via VectorIndex
- Exact lookup via FileStore
- Returns original content (not summaries) per design philosophy
"""

from pathlib import Path

from ai_midlayer.knowledge.models import Chunk, Document, SearchResult
from ai_midlayer.knowledge.store import FileStore
from ai_midlayer.knowledge.index import VectorIndex


class Retriever:
    """Retriever for RAG search.
    
    Combines vector similarity search with document store to provide:
    - Semantic search for finding relevant chunks
    - Access to full original documents (无损存储)
    - Context-aware retrieval
    
    Architecture alignment: L2 Knowledge Layer → RAG 检索
    """
    
    def __init__(self, store: FileStore, index: VectorIndex):
        """Initialize the retriever.
        
        Args:
            store: The file store for document access.
            index: The vector index for semantic search.
        """
        self.store = store
        self.index = index
    
    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        include_context: bool = True
    ) -> list[SearchResult]:
        """Retrieve relevant content for a query.
        
        Args:
            query: The search query.
            top_k: Number of results to return.
            include_context: Whether to include surrounding context.
            
        Returns:
            List of SearchResult with chunks and optional document context.
        """
        # 1. Semantic search
        results = self.index.search(query, top_k=top_k)
        
        if not results:
            return []
        
        # 2. Enrich with document metadata
        for result in results:
            doc = self.store.get_file(result.chunk.doc_id)
            if doc:
                result.doc = doc
                # Add context from document
                if include_context:
                    result.chunk.metadata["document_context"] = self._get_context(
                        doc, result.chunk.start_idx, result.chunk.end_idx
                    )
        
        return results
    
    def _get_context(
        self,
        doc: Document,
        start_idx: int,
        end_idx: int,
        context_chars: int = 200
    ) -> str:
        """Get surrounding context for a chunk.
        
        Args:
            doc: The source document.
            start_idx: Start index of the chunk.
            end_idx: End index of the chunk.
            context_chars: Number of characters to include before/after.
            
        Returns:
            The chunk with surrounding context.
        """
        content = doc.content
        
        # Expand range with context
        ctx_start = max(0, start_idx - context_chars)
        ctx_end = min(len(content), end_idx + context_chars)
        
        # Try to break at word boundaries
        if ctx_start > 0:
            space_idx = content.find(' ', ctx_start)
            if space_idx != -1 and space_idx < start_idx:
                ctx_start = space_idx + 1
        
        if ctx_end < len(content):
            space_idx = content.rfind(' ', end_idx, ctx_end)
            if space_idx != -1:
                ctx_end = space_idx
        
        return content[ctx_start:ctx_end]
    
    def retrieve_by_document(
        self,
        doc_id: str,
        query: str | None = None,
        top_k: int = 10
    ) -> list[SearchResult]:
        """Retrieve content from a specific document.
        
        Args:
            doc_id: The document ID to search within.
            query: Optional query to filter results.
            top_k: Number of results to return.
            
        Returns:
            List of SearchResult from the specified document.
        """
        # Get all chunks from this document
        results = self.index.search(query or "", top_k=top_k * 3)
        
        # Filter to this document
        doc_results = [r for r in results if r.chunk.doc_id == doc_id][:top_k]
        
        # Enrich with document
        doc = self.store.get_file(doc_id)
        for result in doc_results:
            result.doc = doc
        
        return doc_results
    
    def get_full_document(self, doc_id: str) -> Document | None:
        """Get the full original document (无损检索).
        
        Args:
            doc_id: The document ID.
            
        Returns:
            The full Document, or None if not found.
        """
        return self.store.get_file(doc_id)
