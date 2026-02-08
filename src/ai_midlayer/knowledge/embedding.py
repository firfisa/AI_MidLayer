"""Embedding client for custom embedding models.

Supports:
- Local models via sentence-transformers (default)
- OpenAI-compatible API endpoints (e.g., text-embedding-3-small)
- Custom embedding providers (qwen3-embedding-8b, etc.)
"""

import httpx
from typing import Optional


class EmbeddingClient:
    """Client for generating text embeddings."""
    
    def __init__(
        self,
        model: str = "all-MiniLM-L6-v2",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        dimensions: int = 1536,
    ):
        """Initialize the embedding client.
        
        Args:
            model: Model name (e.g., "text-embedding-3-small", "qwen3-embedding-8b")
            api_key: API key for the embedding service
            base_url: Base URL for the API (e.g., "https://api.openai.com/v1")
            dimensions: Expected embedding dimensions
        """
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/") if base_url else None
        self.dimensions = dimensions
        
        self._local_model = None
        self._use_api = api_key is not None and base_url is not None
    
    @property
    def use_api(self) -> bool:
        """Check if using API instead of local model."""
        return self._use_api
    
    def _get_local_model(self):
        """Lazy load local sentence-transformer model."""
        if self._local_model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._local_model = SentenceTransformer(self.model)
            except ImportError:
                raise ImportError(
                    "sentence-transformers is required for local embeddings. "
                    "Install with: pip install sentence-transformers"
                )
        return self._local_model
    
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts.
        
        Args:
            texts: List of text strings to embed.
            
        Returns:
            List of embedding vectors.
        """
        if not texts:
            return []
        
        if self._use_api:
            return self._embed_api(texts)
        else:
            return self._embed_local(texts)
    
    def embed_single(self, text: str) -> list[float]:
        """Generate embedding for a single text.
        
        Args:
            text: Text string to embed.
            
        Returns:
            Embedding vector.
        """
        embeddings = self.embed([text])
        return embeddings[0] if embeddings else []
    
    def _embed_local(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using local model."""
        model = self._get_local_model()
        embeddings = model.encode(texts, convert_to_numpy=True)
        return [e.tolist() for e in embeddings]
    
    def _embed_api(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using OpenAI-compatible API."""
        url = f"{self.base_url}/embeddings"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self.model,
            "input": texts,
        }
        
        # Add dimensions if model supports it
        if "text-embedding-3" in self.model:
            payload["dimensions"] = self.dimensions
        
        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                
                data = response.json()
                
                # Extract embeddings (OpenAI format)
                embeddings = [item["embedding"] for item in data["data"]]
                return embeddings
                
        except httpx.HTTPError as e:
            raise RuntimeError(f"Embedding API error: {e}")
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Unexpected API response format: {e}")


def get_embedding_client(
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    dimensions: int = 1536,
) -> EmbeddingClient:
    """Get an embedding client, optionally from environment config.
    
    Args:
        model: Model name override
        api_key: API key override
        base_url: Base URL override
        dimensions: Embedding dimensions
        
    Returns:
        Configured EmbeddingClient instance.
    """
    import os
    
    return EmbeddingClient(
        model=model or os.getenv("MIDLAYER_EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
        api_key=api_key or os.getenv("MIDLAYER_EMBEDDING_API_KEY"),
        base_url=base_url or os.getenv("MIDLAYER_EMBEDDING_BASE_URL"),
        dimensions=dimensions,
    )
