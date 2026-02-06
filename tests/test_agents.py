"""Tests for agents module."""

from pathlib import Path

import pytest

from ai_midlayer.agents.parser import ParserAgent


class TestParserAgent:
    """Tests for ParserAgent."""
    
    def test_parse_markdown(self, tmp_path):
        """Test parsing markdown file."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Hello\n\nWorld!")
        
        agent = ParserAgent()
        doc = agent.parse(test_file)
        
        assert doc is not None
        assert doc.file_type == "md"
        assert "Hello" in doc.content
    
    def test_parse_text(self, tmp_path):
        """Test parsing text file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Plain text content")
        
        agent = ParserAgent()
        doc = agent.parse(test_file)
        
        assert doc is not None
        assert doc.file_type == "txt"
    
    def test_parse_nonexistent(self, tmp_path):
        """Test parsing nonexistent file."""
        agent = ParserAgent()
        doc = agent.parse(tmp_path / "nonexistent.txt")
        
        assert doc is None
