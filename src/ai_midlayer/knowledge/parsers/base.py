"""Base parser interface."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from ai_midlayer.knowledge.models import Document


class BaseParser(ABC):
    """Abstract base class for file parsers."""
    
    @abstractmethod
    def parse(self, path: str | Path) -> Optional[Document]:
        """Parse file and return Document.
        
        Args:
            path: Path to file
            
        Returns:
            Parsed Document or None if parsing failed
        """
        pass
    
    @abstractmethod
    def supports(self, path: str | Path) -> bool:
        """Check if parser supports this file type.
        
        Args:
            path: Path to file
            
        Returns:
            True if supported
        """
        pass
