"""File storage for the knowledge base - lossless storage with metadata."""

import json
import shutil
from pathlib import Path

from ai_midlayer.knowledge.models import Document


class FileStore:
    """Lossless file storage for the knowledge base.
    
    Stores original files and their parsed representations.
    """
    
    def __init__(self, kb_path: str | Path):
        """Initialize the file store.
        
        Args:
            kb_path: Path to the knowledge base directory.
        """
        self.kb_path = Path(kb_path)
        self.raw_dir = self.kb_path / "raw"
        self.parsed_dir = self.kb_path / "parsed"
        self.index_file = self.kb_path / "index.json"
        
        # Ensure directories exist
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.parsed_dir.mkdir(parents=True, exist_ok=True)
        
        # Load or create index
        self._index: dict[str, dict] = self._load_index()
    
    def _load_index(self) -> dict[str, dict]:
        """Load the document index from disk."""
        if self.index_file.exists():
            return json.loads(self.index_file.read_text())
        return {}
    
    def _save_index(self) -> None:
        """Save the document index to disk."""
        self.index_file.write_text(json.dumps(self._index, indent=2, default=str))
    
    def add_file(self, path: str | Path) -> str:
        """Add a file to the knowledge base.
        
        Args:
            path: Path to the file to add.
            
        Returns:
            The document ID assigned to this file.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        
        # Create document from file
        doc = Document.from_file(path)
        
        # Copy original file to raw storage (lossless)
        raw_dest = self.raw_dir / f"{doc.id}_{path.name}"
        shutil.copy2(path, raw_dest)
        
        # Save parsed document (without raw_content to save space)
        parsed_doc = doc.model_dump()
        parsed_doc["raw_content"] = None  # Don't duplicate
        parsed_doc["raw_path"] = str(raw_dest)
        
        parsed_path = self.parsed_dir / f"{doc.id}.json"
        parsed_path.write_text(json.dumps(parsed_doc, indent=2, default=str))
        
        # Update index
        self._index[doc.id] = {
            "file_name": doc.file_name,
            "file_type": doc.file_type,
            "source_path": doc.source_path,
            "raw_path": str(raw_dest),
            "parsed_path": str(parsed_path),
            "created_at": str(doc.created_at),
        }
        self._save_index()
        
        return doc.id
    
    def get_file(self, doc_id: str) -> Document | None:
        """Get a document by ID.
        
        Args:
            doc_id: The document ID.
            
        Returns:
            The Document, or None if not found.
        """
        if doc_id not in self._index:
            return None
        
        parsed_path = Path(self._index[doc_id]["parsed_path"])
        if not parsed_path.exists():
            return None
        
        data = json.loads(parsed_path.read_text())
        
        # Load raw content if needed
        raw_path = Path(data.get("raw_path", ""))
        if raw_path.exists():
            data["raw_content"] = raw_path.read_bytes()
        
        return Document.model_validate(data)
    
    def list_files(self) -> list[dict]:
        """List all files in the knowledge base.
        
        Returns:
            List of file metadata dictionaries.
        """
        return [
            {"id": doc_id, **meta}
            for doc_id, meta in self._index.items()
        ]
    
    def remove_file(self, doc_id: str) -> bool:
        """Remove a file from the knowledge base.
        
        Args:
            doc_id: The document ID to remove.
            
        Returns:
            True if removed, False if not found.
        """
        if doc_id not in self._index:
            return False
        
        meta = self._index[doc_id]
        
        # Remove files
        raw_path = Path(meta["raw_path"])
        parsed_path = Path(meta["parsed_path"])
        
        if raw_path.exists():
            raw_path.unlink()
        if parsed_path.exists():
            parsed_path.unlink()
        
        # Update index
        del self._index[doc_id]
        self._save_index()
        
        return True
