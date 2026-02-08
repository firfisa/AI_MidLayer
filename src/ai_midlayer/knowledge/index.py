"""Vector index for semantic search using LanceDB.

Implements the vector_store component from the system architecture:
- project_kb/index/vector_store/

Uses LanceDB for embedded vector storage with semantic search.
Supports custom embedding models via EmbeddingClient.
"""

from pathlib import Path
from typing import Any, Optional
import os

import lancedb
import pyarrow as pa
from pydantic import BaseModel, Field

from ai_midlayer.knowledge.models import Chunk, Document, SearchResult
from ai_midlayer.knowledge.embedding import EmbeddingClient


class ChunkEmbedding(BaseModel):
    """A chunk with its embedding for storage in LanceDB."""
    
    id: str
    doc_id: str
    content: str
    start_idx: int
    end_idx: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class VectorIndex:
    """Vector index for semantic search using LanceDB.
    
    Provides:
    - Document chunking and indexing
    - Semantic similarity search with custom embeddings
    - Support for OpenAI-compatible embedding APIs
    
    Architecture alignment: L2 Knowledge Layer → index/vector_store
    """
    
    TABLE_NAME = "chunks"
    CHUNK_SIZE = 500  # characters per chunk
    CHUNK_OVERLAP = 100  # overlap between chunks
    
    def __init__(
        self,
        kb_path: str | Path,
        embedding_model: Optional[str] = None,
        embedding_api_key: Optional[str] = None,
        embedding_base_url: Optional[str] = None,
        embedding_dimensions: int = 1536,
    ):
        """Initialize the vector index.
        
        Args:
            kb_path: Path to the knowledge base directory.
            embedding_model: Embedding model name (default from env or "all-MiniLM-L6-v2")
            embedding_api_key: API key for embedding service (optional)
            embedding_base_url: Base URL for embedding API (optional)
            embedding_dimensions: Embedding vector dimensions
        """
        self.kb_path = Path(kb_path)
        self.index_dir = self.kb_path / "index" / "vector_store"
        self.index_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize embedding client
        self._embedding = EmbeddingClient(
            model=embedding_model or os.getenv("MIDLAYER_EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
            api_key=embedding_api_key or os.getenv("MIDLAYER_EMBEDDING_API_KEY"),
            base_url=embedding_base_url or os.getenv("MIDLAYER_EMBEDDING_BASE_URL"),
            dimensions=embedding_dimensions,
        )
        
        # Initialize LanceDB
        self.db = lancedb.connect(str(self.index_dir))
        self._table = None
        self._embedding_dimensions = embedding_dimensions
    
    @property
    def embedding_client(self) -> EmbeddingClient:
        """Get the embedding client."""
        return self._embedding
    
    @property
    def table(self):
        """Get or create the chunks table."""
        if self._table is None:
            try:
                self._table = self.db.open_table(self.TABLE_NAME)
            except Exception:
                # Table doesn't exist yet, will be created on first insert
                pass
        return self._table
    
    def _chunk_text(self, text: str, doc_id: str) -> list[Chunk]:
        """Split text into overlapping chunks.
        
        Args:
            text: The text to chunk.
            doc_id: The document ID for the chunks.
            
        Returns:
            List of Chunk objects.
        """
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + self.CHUNK_SIZE
            chunk_text = text[start:end]
            
            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence endings
                for sep in ['. ', '。', '\n\n', '\n']:
                    last_sep = chunk_text.rfind(sep)
                    if last_sep > self.CHUNK_SIZE // 2:
                        end = start + last_sep + len(sep)
                        chunk_text = text[start:end]
                        break
            
            chunk = Chunk(
                content=chunk_text.strip(),
                doc_id=doc_id,
                start_idx=start,
                end_idx=end,
            )
            chunks.append(chunk)
            
            # Move to next chunk with overlap
            start = end - self.CHUNK_OVERLAP
            if start >= len(text):
                break
        
        return chunks
    
    def index_document(self, doc: Document) -> int:
        """Index a document by chunking and storing in vector DB.
        
        Args:
            doc: The document to index.
            
        Returns:
            Number of chunks indexed.
        """
        if not doc.content:
            return 0
        
        # Chunk the document
        chunks = self._chunk_text(doc.content, doc.id)
        
        if not chunks:
            return 0
        
        # Generate embeddings for all chunks
        chunk_texts = [c.content for c in chunks]
        embeddings = self._embedding.embed(chunk_texts)
        
        # Prepare data for LanceDB with embeddings
        data = []
        for chunk, embedding in zip(chunks, embeddings):
            data.append({
                "id": chunk.id,
                "doc_id": chunk.doc_id,
                "content": chunk.content,
                "start_idx": chunk.start_idx,
                "end_idx": chunk.end_idx,
                "file_name": doc.file_name,
                "file_type": doc.file_type,
                "vector": embedding,  # Store embedding
            })
        
        # Insert into LanceDB
        if self.table is None:
            # Create table with first batch
            self._table = self.db.create_table(
                self.TABLE_NAME,
                data,
                mode="overwrite"
            )
        else:
            self._table.add(data)
        
        # Update document with chunks
        doc.chunks = chunks
        
        return len(chunks)
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        filter_doc_id: str | None = None
    ) -> list[SearchResult]:
        """Search for relevant chunks using semantic similarity.
        
        Args:
            query: The search query.
            top_k: Number of results to return.
            filter_doc_id: Optional document ID to filter results.
            
        Returns:
            List of SearchResult objects.
        """
        if self.table is None:
            return []
        
        try:
            # Generate query embedding
            query_embedding = self._embedding.embed_single(query)
            
            # Vector search with LanceDB
            results = (
                self.table.search(query_embedding)
                .limit(top_k)
                .to_list()
            )
        except Exception as e:
            # Fallback to FTS if vector search fails
            try:
                results = (
                    self.table.search(query)
                    .limit(top_k)
                    .to_list()
                )
            except Exception:
                # Final fallback
                results = self.table.to_pandas().head(top_k).to_dict('records')
        
        # Convert to SearchResult objects
        search_results = []
        for i, row in enumerate(results):
            chunk = Chunk(
                id=row.get("id", ""),
                doc_id=row.get("doc_id", ""),
                content=row.get("content", ""),
                start_idx=row.get("start_idx", 0),
                end_idx=row.get("end_idx", 0),
                metadata={
                    "file_name": row.get("file_name", ""),
                    "file_type": row.get("file_type", ""),
                }
            )
            
            # Use _distance from LanceDB (lower = more similar)
            # Convert to similarity score (higher = better)
            distance = row.get("_distance", i)
            if isinstance(distance, (int, float)):
                score = 1.0 / (1.0 + distance)
            else:
                score = 1.0 - (i / max(len(results), 1))
            
            search_results.append(SearchResult(
                chunk=chunk,
                score=score,
            ))
        
        return search_results
    
    def remove_document(self, doc_id: str) -> int:
        """Remove all chunks for a document.
        
        Args:
            doc_id: The document ID to remove.
            
        Returns:
            Number of chunks removed.
        """
        if self.table is None:
            return 0
        
        try:
            # Count before deletion
            df = self.table.to_pandas()
            count_before = len(df[df["doc_id"] == doc_id])
            
            # Delete chunks for this document
            self._table.delete(f"doc_id = '{doc_id}'")
            
            return count_before
        except Exception:
            return 0
    
    def get_stats(self) -> dict:
        """Get statistics about the vector index.
        
        Returns:
            Dictionary with index statistics.
        """
        if self.table is None:
            return {
                "total_chunks": 0,
                "total_documents": 0,
                "embedding_model": self._embedding.model,
                "use_api": self._embedding.use_api,
            }
        
        try:
            df = self.table.to_pandas()
            return {
                "total_chunks": len(df),
                "total_documents": df["doc_id"].nunique(),
                "embedding_model": self._embedding.model,
                "use_api": self._embedding.use_api,
            }
        except Exception:
            return {
                "total_chunks": 0,
                "total_documents": 0,
                "embedding_model": self._embedding.model,
                "use_api": self._embedding.use_api,
            }
