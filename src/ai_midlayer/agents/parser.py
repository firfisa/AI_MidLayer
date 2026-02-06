"""Parser Agent for file parsing."""

# Placeholder - will be fully implemented in Step 4
from pathlib import Path
from typing import Any

from ai_midlayer.agents.base import Agent, AgentState
from ai_midlayer.knowledge.models import Document


class ParserAgent(Agent):
    """Agent for parsing files into Documents.
    
    Supports: Markdown, TXT, PDF (basic)
    
    TODO: Full implementation with Unstructured.io in Step 4
    """
    
    def __init__(self):
        super().__init__(max_iterations=1)  # Single pass for now
    
    def observe(self, state: AgentState) -> Any:
        """Observe the input file."""
        path = Path(state.input)
        return {
            "path": str(path),
            "exists": path.exists(),
            "type": path.suffix.lstrip(".").lower() if path.exists() else None,
            "size": path.stat().st_size if path.exists() else 0,
        }
    
    def orient(self, state: AgentState, observation: Any) -> Any:
        """Determine parsing strategy."""
        if not observation["exists"]:
            return {"error": "File not found"}
        
        file_type = observation["type"]
        if file_type in ("md", "txt", "json", "py", "yml", "yaml"):
            return {"strategy": "text", "encoding": "utf-8"}
        elif file_type == "pdf":
            return {"strategy": "pdf", "tool": "unstructured"}
        else:
            return {"strategy": "binary", "warning": "Unknown file type"}
    
    def decide(self, state: AgentState, orientation: Any) -> Any:
        """Decide how to parse."""
        if "error" in orientation:
            return {"action": "abort", "reason": orientation["error"]}
        return {"action": "parse", "strategy": orientation["strategy"]}
    
    def act(self, state: AgentState, decision: Any) -> Any:
        """Execute parsing."""
        if decision["action"] == "abort":
            state.is_complete = True
            state.output = None
            return {"error": decision["reason"]}
        
        # Basic parsing (will be enhanced in Step 4)
        doc = Document.from_file(state.input)
        state.output = doc
        state.is_complete = True
        return {"success": True, "doc_id": doc.id}
    
    def parse(self, path: str | Path) -> Document | None:
        """Convenience method to parse a file.
        
        Args:
            path: Path to the file to parse.
            
        Returns:
            Parsed Document, or None if parsing failed.
        """
        return self.run(str(path))
