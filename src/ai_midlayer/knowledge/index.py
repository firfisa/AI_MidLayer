"""Vector index for semantic search using LanceDB."""

# Placeholder - will be implemented in Step 3

class VectorIndex:
    """Vector index for semantic search.
    
    TODO: Implement in Step 3
    """
    
    def __init__(self, kb_path: str):
        self.kb_path = kb_path
    
    def index_document(self, doc) -> None:
        """Index a document."""
        raise NotImplementedError("Step 3")
    
    def search(self, query: str, top_k: int = 5):
        """Search for documents."""
        raise NotImplementedError("Step 3")
