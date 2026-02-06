"""Retriever for RAG search."""

# Placeholder - will be implemented in Step 5

class Retriever:
    """Retriever for RAG search.
    
    TODO: Implement in Step 5
    """
    
    def __init__(self, store, index):
        self.store = store
        self.index = index
    
    def retrieve(self, query: str, top_k: int = 5):
        """Retrieve relevant content."""
        raise NotImplementedError("Step 5")
