"""Tests for Phase 2 Agent architecture."""

import tempfile
from pathlib import Path

import pytest

from ai_midlayer.agents.protocols import AgentPhase, AgentState
from ai_midlayer.agents.base import BaseAgent
from ai_midlayer.agents.parser import ParserAgent, ParserState
from ai_midlayer.agents.structure import StructureAgent, DocumentType
from ai_midlayer.knowledge.models import Document


class TestAgentState:
    """Tests for AgentState."""
    
    def test_initial_state(self):
        """Test initial state values."""
        state = AgentState()
        
        assert state.phase == AgentPhase.OBSERVE
        assert state.iteration == 0
        assert state.is_complete is False
        assert len(state.observations) == 0
    
    def test_state_mutations(self):
        """Test state mutation methods."""
        state = AgentState()
        
        state.add_observation("obs1")
        state.add_decision("dec1")
        state.add_action("act1")
        state.add_reflection("ref1")
        
        assert len(state.observations) == 1
        assert len(state.decisions) == 1
        assert len(state.actions) == 1
        assert len(state.reflections) == 1


class TestParserAgent:
    """Tests for ParserAgent with OODA loop."""
    
    def test_parse_text_file(self, tmp_path):
        """Test parsing a text file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello World\nThis is a test file.")
        
        agent = ParserAgent()
        result = agent.parse(str(test_file))
        
        assert result is not None
        assert result.file_type == "txt"
        assert "Hello World" in result.content
    
    def test_parse_markdown_file(self, tmp_path):
        """Test parsing a markdown file."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Header\n\nParagraph content here.")
        
        agent = ParserAgent()
        result = agent.parse(str(test_file))
        
        assert result is not None
        assert result.file_type == "md"
        assert "Header" in result.content
    
    def test_parse_nonexistent_file(self):
        """Test parsing a nonexistent file."""
        agent = ParserAgent()
        result = agent.parse("/nonexistent/file.txt")
        
        assert result is None
    
    def test_parse_quality_evaluation(self, tmp_path):
        """Test quality score in parsed document."""
        test_file = tmp_path / "quality.md"
        test_file.write_text("# Good Content\n\n" + "This is quality content. " * 20)
        
        agent = ParserAgent()
        result = agent.parse(str(test_file))
        
        assert result is not None
        assert "quality_score" in result.metadata
        assert result.metadata["quality_score"] > 0


class TestStructureAgent:
    """Tests for StructureAgent."""
    
    def test_analyze_markdown(self):
        """Test structure analysis of markdown document."""
        doc = Document(
            id="test-doc",
            source_path="/test/file.md",
            file_name="file.md",
            file_type="md",
            content="# Introduction\n\nFirst paragraph.\n\n## Details\n\nSecond paragraph."
        )
        
        agent = StructureAgent()
        structure = agent.analyze(doc)
        
        assert structure is not None
        assert structure.doc_id == "test-doc"
        assert len(structure.sections) >= 2
    
    def test_detect_document_type(self):
        """Test document type detection."""
        # Technical document
        doc = Document(
            id="tech-doc",
            source_path="/test/api.md",
            file_name="api.md",
            file_type="md",
            content="# API Documentation\n\nThis is the implementation guide.\n\nclass Example:\n    def method(self):"
        )
        
        agent = StructureAgent()
        structure = agent.analyze(doc)
        
        assert structure is not None
        assert structure.doc_type in [DocumentType.TECHNICAL_DOC, DocumentType.CODE, DocumentType.GENERAL]
    
    def test_generate_tags(self):
        """Test tag generation."""
        doc = Document(
            id="python-doc",
            source_path="/test/script.py",
            file_name="script.py",
            file_type="py",
            content="import pandas\ndef process_data():\n    pass"
        )
        
        agent = StructureAgent()
        structure = agent.analyze(doc)
        
        assert structure is not None
        assert len(structure.tags) > 0
        assert "py" in structure.tags


class TestDocumentPipeline:
    """Tests for DocumentPipeline."""
    
    def test_process_file(self, tmp_path):
        """Test processing a single file through pipeline."""
        from ai_midlayer.orchestrator import DocumentPipeline
        
        # Create test file
        test_file = tmp_path / "process_test.md"
        test_file.write_text("# Test Document\n\nContent for processing.")
        
        # Create pipeline with minimal components
        pipeline = DocumentPipeline(
            parser=ParserAgent(),
            structure_agent=StructureAgent(),
        )
        
        result = pipeline.process(str(test_file))
        
        assert result["success"] or len(result["errors"]) > 0
        assert result["document"] is not None
        assert result["structure"] is not None
