"""Retriever for RAG search - combines FileStore and VectorIndex.

Implements hybrid retrieval from the system architecture:
- Semantic search via VectorIndex
- Exact lookup via FileStore
- BM25 full-text search (optional hybrid mode)
- Returns original content (not summaries) per design philosophy
"""

from pathlib import Path
from typing import TYPE_CHECKING

from ai_midlayer.knowledge.models import Chunk, Document, SearchResult
from ai_midlayer.knowledge.store import FileStore
from ai_midlayer.knowledge.index import VectorIndex

if TYPE_CHECKING:
    from ai_midlayer.knowledge.bm25 import BM25Index


class Retriever:
    """Retriever for RAG search.
    
    Combines vector similarity search with document store to provide:
    - Semantic search for finding relevant chunks
    - BM25 full-text search (optional)
    - RRF fusion for hybrid mode
    - Access to full original documents (无损存储)
    - Context-aware retrieval
    
    Architecture alignment: L2 Knowledge Layer → RAG 检索
    """
    
    def __init__(
        self,
        store: FileStore,
        index: VectorIndex,
        bm25_index: "BM25Index | None" = None,
    ):
        """Initialize the retriever.
        
        Args:
            store: The file store for document access.
            index: The vector index for semantic search.
            bm25_index: Optional BM25 index for hybrid search.
        """
        self.store = store
        self.index = index
        self.bm25_index = bm25_index
        self._hybrid_mode = bm25_index is not None
    
    @property
    def hybrid_enabled(self) -> bool:
        """Check if hybrid search is enabled."""
        return self._hybrid_mode and self.bm25_index is not None
    
    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        include_context: bool = True,
        use_hybrid: bool | None = None,
    ) -> list[SearchResult]:
        """Retrieve relevant content for a query.
        
        Args:
            query: The search query.
            top_k: Number of results to return.
            include_context: Whether to include surrounding context.
            use_hybrid: Force hybrid mode on/off. None = auto (use if BM25 available).
            
        Returns:
            List of SearchResult with chunks and optional document context.
        """
        # Determine search mode
        hybrid = use_hybrid if use_hybrid is not None else self.hybrid_enabled
        
        if hybrid and self.bm25_index:
            results = self._hybrid_search(query, top_k)
        else:
            # Vector-only search
            results = self.index.search(query, top_k=top_k)
        
        if not results:
            return []
        
        # Enrich with document metadata
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
    
    def _hybrid_search(self, query: str, top_k: int) -> list[SearchResult]:
        """Perform hybrid search using both Vector and BM25.
        
        Uses RRF (Reciprocal Rank Fusion) to combine results.
        
        Args:
            query: The search query.
            top_k: Number of results to return.
            
        Returns:
            Fused search results.
        """
        from ai_midlayer.rag.fusion import reciprocal_rank_fusion, detect_strong_signal
        
        # Search with both methods
        vector_results = self.index.search(query, top_k=top_k * 2)
        bm25_results = self.bm25_index.search(query, top_k=top_k * 2) if self.bm25_index else []
        
        # Check for strong signal (exact match in BM25)
        if bm25_results:
            signal = detect_strong_signal(bm25_results)
            if signal.is_strong:
                # Strong BM25 signal, skip fusion
                for r in bm25_results[:top_k]:
                    r.chunk.metadata["search_source"] = "bm25 (strong signal)"
                return bm25_results[:top_k]
        
        # RRF fusion
        if not bm25_results:
            # No BM25 results, return vector only
            for r in vector_results[:top_k]:
                r.chunk.metadata["search_source"] = "vector"
            return vector_results[:top_k]
        
        fusion_results = reciprocal_rank_fusion(
            result_lists=[bm25_results, vector_results],
            weights=[2.0, 1.0],  # BM25 weighted higher (like QMD)
            top_n=top_k,
        )
        
        # Extract SearchResult and add source info
        results = []
        for fr in fusion_results:
            fr.result.chunk.metadata["search_source"] = "hybrid"
            fr.result.chunk.metadata["rrf_score"] = fr.rrf_score
            fr.result.chunk.metadata["sources"] = ", ".join(fr.sources)
            results.append(fr.result)
        
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
