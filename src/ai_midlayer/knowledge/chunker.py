"""Smart chunker with document structure awareness.

Features:
- Heading-aware splitting for Markdown
- Code-aware splitting (functions, classes)
- Semantic paragraph detection
- Overlap handling

Usage:
    chunker = SmartChunker()
    chunks = chunker.chunk(text, doc_type="markdown")
"""

import re
from dataclasses import dataclass, field
from typing import Optional

from ai_midlayer.knowledge.models import Chunk


@dataclass
class Section:
    """Document section with heading info."""
    
    title: str
    level: int  # 1-6 for headings
    content: str
    start_idx: int
    end_idx: int


class SmartChunker:
    """Smart document chunker with structure awareness.
    
    Splits documents intelligently based on:
    - Markdown headings
    - Code structure (functions, classes)
    - Semantic paragraphs
    """
    
    DEFAULT_CHUNK_SIZE = 500
    DEFAULT_OVERLAP = 100
    MIN_CHUNK_SIZE = 100
    
    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overlap: int = DEFAULT_OVERLAP,
        respect_headings: bool = True,
        respect_code_blocks: bool = True,
    ):
        """Initialize chunker.
        
        Args:
            chunk_size: Target chunk size in characters
            overlap: Overlap between chunks
            respect_headings: Keep heading sections together
            respect_code_blocks: Keep code blocks together
        """
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.respect_headings = respect_headings
        self.respect_code_blocks = respect_code_blocks
    
    def chunk(
        self,
        text: str,
        doc_id: str,
        doc_type: str = "text",
        metadata: Optional[dict] = None,
    ) -> list[Chunk]:
        """Split text into chunks.
        
        Args:
            text: Document text
            doc_id: Document ID for chunk association
            doc_type: Document type (markdown, python, text)
            metadata: Additional metadata to include
            
        Returns:
            List of Chunk objects
        """
        if not text or not text.strip():
            return []
        
        base_metadata = metadata or {}
        
        # Route to appropriate chunking strategy
        if doc_type in ("markdown", "md"):
            return self._chunk_markdown(text, doc_id, base_metadata)
        elif doc_type in ("python", "py"):
            return self._chunk_python(text, doc_id, base_metadata)
        else:
            return self._chunk_text(text, doc_id, base_metadata)
    
    def _chunk_markdown(self, text: str, doc_id: str, metadata: dict) -> list[Chunk]:
        """Chunk Markdown with heading awareness.
        
        Strategy:
        1. Detect heading structure
        2. Split at heading boundaries
        3. Further split large sections
        """
        sections = self._detect_markdown_sections(text)
        
        if not sections:
            return self._chunk_text(text, doc_id, metadata)
        
        chunks = []
        for section in sections:
            section_metadata = {
                **metadata,
                "section_title": section.title,
                "heading_level": section.level,
            }
            
            # If section fits in one chunk, keep it together
            if len(section.content) <= self.chunk_size * 1.5:
                chunk = Chunk(
                    doc_id=doc_id,
                    content=section.content.strip(),
                    start_idx=section.start_idx,
                    end_idx=section.end_idx,
                    metadata=section_metadata,
                )
                chunks.append(chunk)
            else:
                # Split large section
                sub_chunks = self._chunk_text(
                    section.content,
                    doc_id,
                    section_metadata,
                    base_idx=section.start_idx,
                )
                chunks.extend(sub_chunks)
        
        return chunks
    
    def _detect_markdown_sections(self, text: str) -> list[Section]:
        """Detect Markdown heading sections."""
        # Match Markdown headings (# through ######)
        heading_pattern = r'^(#{1,6})\s+(.+)$'
        
        lines = text.split('\n')
        sections = []
        current_section = None
        current_lines = []
        current_start = 0
        
        char_pos = 0
        for i, line in enumerate(lines):
            match = re.match(heading_pattern, line)
            
            if match:
                # Save previous section
                if current_section is not None or current_lines:
                    content = '\n'.join(current_lines)
                    if current_section:
                        sections.append(Section(
                            title=current_section["title"],
                            level=current_section["level"],
                            content=content,
                            start_idx=current_start,
                            end_idx=char_pos,
                        ))
                    elif content.strip():
                        # Content before first heading
                        sections.append(Section(
                            title="",
                            level=0,
                            content=content,
                            start_idx=0,
                            end_idx=char_pos,
                        ))
                
                # Start new section
                level = len(match.group(1))
                title = match.group(2)
                current_section = {"title": title, "level": level}
                current_lines = [line]
                current_start = char_pos
            else:
                current_lines.append(line)
            
            char_pos += len(line) + 1  # +1 for newline
        
        # Add final section
        if current_lines:
            content = '\n'.join(current_lines)
            if current_section:
                sections.append(Section(
                    title=current_section["title"],
                    level=current_section["level"],
                    content=content,
                    start_idx=current_start,
                    end_idx=len(text),
                ))
            elif content.strip():
                sections.append(Section(
                    title="",
                    level=0,
                    content=content,
                    start_idx=current_start,
                    end_idx=len(text),
                ))
        
        return sections
    
    def _chunk_python(self, text: str, doc_id: str, metadata: dict) -> list[Chunk]:
        """Chunk Python code with function/class awareness.
        
        Strategy:
        1. Detect top-level functions and classes
        2. Keep each as a chunk if possible
        3. Split large functions/classes
        """
        # Pattern for top-level def/class
        pattern = r'^(def\s+\w+|class\s+\w+)'
        
        lines = text.split('\n')
        blocks = []
        current_block_start = 0
        current_block_lines = []
        current_name = None
        
        for i, line in enumerate(lines):
            # Check if this is a new top-level definition
            if not line.startswith(' ') and not line.startswith('\t'):
                match = re.match(pattern, line)
                if match:
                    # Save previous block
                    if current_block_lines:
                        blocks.append({
                            "name": current_name,
                            "lines": current_block_lines,
                            "start_line": current_block_start,
                        })
                    
                    current_block_start = i
                    current_block_lines = [line]
                    current_name = match.group(1)
                    continue
            
            current_block_lines.append(line)
        
        # Add final block
        if current_block_lines:
            blocks.append({
                "name": current_name,
                "lines": current_block_lines,
                "start_line": current_block_start,
            })
        
        # Convert blocks to chunks
        chunks = []
        char_pos = 0
        
        for block in blocks:
            content = '\n'.join(block["lines"])
            block_metadata = {
                **metadata,
                "code_block": block["name"] or "module",
            }
            
            if len(content) <= self.chunk_size * 2:
                # Keep block together
                end_pos = char_pos + len(content)
                chunk = Chunk(
                    doc_id=doc_id,
                    content=content.strip(),
                    start_idx=char_pos,
                    end_idx=end_pos,
                    metadata=block_metadata,
                )
                chunks.append(chunk)
            else:
                # Split large block
                sub_chunks = self._chunk_text(content, doc_id, block_metadata, base_idx=char_pos)
                chunks.extend(sub_chunks)
            
            char_pos += len(content) + 1
        
        return chunks if chunks else self._chunk_text(text, doc_id, metadata)
    
    def _chunk_text(
        self,
        text: str,
        doc_id: str,
        metadata: dict,
        base_idx: int = 0,
    ) -> list[Chunk]:
        """Basic text chunking with overlap.
        
        Tries to break at sentence/paragraph boundaries.
        """
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + self.chunk_size
            chunk_text = text[start:end]
            
            # Try to break at sentence/paragraph boundary
            if end < len(text):
                best_break = self._find_break_point(chunk_text)
                if best_break > self.chunk_size // 2:
                    end = start + best_break
                    chunk_text = text[start:end]
            
            chunk = Chunk(
                doc_id=doc_id,
                content=chunk_text.strip(),
                start_idx=base_idx + start,
                end_idx=base_idx + end,
                metadata=metadata.copy(),
            )
            chunks.append(chunk)
            
            # Move with overlap
            start = end - self.overlap
            if start >= len(text):
                break
        
        return chunks
    
    def _find_break_point(self, text: str) -> int:
        """Find best break point in text.
        
        Prefers (in order):
        1. Paragraph break (double newline)
        2. Sentence end (. ! ?)
        3. Single newline
        4. Space
        """
        # Paragraph break
        idx = text.rfind('\n\n')
        if idx > len(text) // 2:
            return idx + 2
        
        # Sentence end
        for sep in ['. ', '。', '! ', '? ']:
            idx = text.rfind(sep)
            if idx > len(text) // 2:
                return idx + len(sep)
        
        # Newline
        idx = text.rfind('\n')
        if idx > len(text) // 2:
            return idx + 1
        
        # Space
        idx = text.rfind(' ')
        if idx > len(text) // 3:
            return idx + 1
        
        return len(text)


def chunk_document(
    text: str,
    doc_id: str,
    doc_type: str = "text",
    chunk_size: int = 500,
    overlap: int = 100,
) -> list[Chunk]:
    """Convenience function to chunk a document.
    
    Args:
        text: Document text
        doc_id: Document ID
        doc_type: Type of document (markdown, python, text)
        chunk_size: Target chunk size
        overlap: Chunk overlap
        
    Returns:
        List of chunks
    """
    chunker = SmartChunker(chunk_size=chunk_size, overlap=overlap)
    return chunker.chunk(text, doc_id, doc_type)
