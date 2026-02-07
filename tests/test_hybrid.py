"""Tests for BM25 index, RRF fusion, and HybridRetriever."""

import tempfile
import pytest
from pathlib import Path

from ai_midlayer.knowledge.models import Document, Chunk, SearchResult
from ai_midlayer.knowledge.bm25 import BM25Index
from ai_midlayer.rag.fusion import (
    reciprocal_rank_fusion,
    position_aware_blend,
    detect_strong_signal,
    FusionResult,
)


class TestBM25Index:
    """BM25 索引测试。"""
    
    def test_index_and_search(self):
        """测试索引和搜索基本功能。"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test_bm25.db"
            index = BM25Index(db_path)
            
            # 创建测试文档
            doc = Document(
                id="doc1",
                content="Python is a programming language that is widely used for web development.",
                file_name="python.md",
                source_path="/test/python.md",
                file_type="markdown",
            )
            
            # 索引文档
            chunks = index.index_document(doc)
            assert chunks > 0
            
            # 搜索
            results = index.search("Python programming", top_k=5)
            assert len(results) > 0
            assert "Python" in results[0].chunk.content
    
    def test_search_no_results(self):
        """测试无结果的搜索。"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test_bm25.db"
            index = BM25Index(db_path)
            
            doc = Document(
                id="doc1",
                content="Hello world",
                file_name="test.md",
                source_path="/test/test.md",
                file_type="markdown",
            )
            index.index_document(doc)
            
            # 搜索不存在的词
            results = index.search("nonexistent_xyz_123", top_k=5)
            assert len(results) == 0
    
    def test_chinese_content(self):
        """测试中文内容索引和搜索。"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test_bm25.db"
            index = BM25Index(db_path)
            
            doc = Document(
                id="doc1",
                content="人工智能是计算机科学的一个分支，它试图理解智能的本质。",
                file_name="ai.md",
                source_path="/test/ai.md",
                file_type="markdown",
            )
            
            chunks = index.index_document(doc)
            assert chunks > 0
            
            # 搜索中文
            results = index.search("人工智能", top_k=5)
            assert len(results) > 0
    
    def test_remove_document(self):
        """测试删除文档。"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test_bm25.db"
            index = BM25Index(db_path)
            
            doc = Document(
                id="doc1",
                content="Test content for removal",
                file_name="test.md",
                source_path="/test/test.md",
                file_type="markdown",
            )
            index.index_document(doc)
            
            # 验证存在
            stats = index.get_stats()
            assert stats["total_documents"] == 1
            
            # 删除
            index.remove_document("doc1")
            
            # 验证删除
            stats = index.get_stats()
            assert stats["total_documents"] == 0
    
    def test_chunking(self):
        """测试长文档分块。"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "test_bm25.db"
            index = BM25Index(db_path)
            
            # 创建长文档 (超过 800 字符)
            long_content = "This is a test. " * 200  # 约 3200 字符
            doc = Document(
                id="doc1",
                content=long_content,
                file_name="long.md",
                source_path="/test/long.md",
                file_type="markdown",
            )
            
            chunks = index.index_document(doc)
            assert chunks > 1  # 应该有多个 chunks


class TestRRFFusion:
    """RRF 融合测试。"""
    
    def _make_result(self, doc_id: str, score: float, content: str = "test") -> SearchResult:
        """创建测试用 SearchResult。"""
        chunk = Chunk(
            id=f"chunk_{doc_id}",
            doc_id=doc_id,
            content=content,
            start_idx=0,
            end_idx=len(content),
            metadata={"file_name": f"{doc_id}.md"}
        )
        return SearchResult(chunk=chunk, score=score)
    
    def test_single_list(self):
        """测试单个列表的融合。"""
        results = [
            self._make_result("doc1", 0.9),
            self._make_result("doc2", 0.8),
            self._make_result("doc3", 0.7),
        ]
        
        fused = reciprocal_rank_fusion([results])
        
        assert len(fused) == 3
        # 第一名应该有 top_rank_bonus
        assert fused[0].is_top_rank
        assert fused[0].rrf_score > fused[1].rrf_score
    
    def test_multiple_lists(self):
        """测试多个列表的融合。"""
        list1 = [
            self._make_result("doc1", 0.9),
            self._make_result("doc2", 0.8),
        ]
        list2 = [
            self._make_result("doc2", 0.95),
            self._make_result("doc3", 0.85),
        ]
        
        fused = reciprocal_rank_fusion([list1, list2])
        
        # doc2 出现在两个列表中，分数应该更高
        doc2_result = next(f for f in fused if f.result.chunk.doc_id == "doc2")
        doc1_result = next(f for f in fused if f.result.chunk.doc_id == "doc1")
        
        assert doc2_result.rrf_score > doc1_result.rrf_score
    
    def test_weighted_fusion(self):
        """测试加权融合。"""
        list1 = [self._make_result("doc1", 0.9)]  # 权重 2.0
        list2 = [self._make_result("doc2", 0.9)]  # 权重 1.0
        
        fused = reciprocal_rank_fusion([list1, list2], weights=[2.0, 1.0])
        
        # 权重更高的列表结果分数应该更高
        doc1_result = next(f for f in fused if f.result.chunk.doc_id == "doc1")
        doc2_result = next(f for f in fused if f.result.chunk.doc_id == "doc2")
        
        assert doc1_result.rrf_score > doc2_result.rrf_score


class TestPositionAwareBlend:
    """位置感知混合测试。"""
    
    def test_top3_prefers_rrf(self):
        """测试 Top 1-3 更信任 RRF。"""
        rrf_score = 0.5
        rerank_score = 0.3
        
        # Rank 0 (Top 1): 75% RRF
        score_rank0 = position_aware_blend(rrf_score, rerank_score, 0)
        
        # Rank 10: 40% RRF
        score_rank10 = position_aware_blend(rrf_score, rerank_score, 10)
        
        # 对于高 RRF 分数，Top 排名应该产生更高的混合分数
        assert score_rank0 > score_rank10
    
    def test_lower_ranks_prefer_rerank(self):
        """测试低排名更信任 Rerank。"""
        rrf_score = 0.2
        rerank_score = 0.9
        
        # Rank 0: 75% RRF + 25% Rerank
        score_rank0 = position_aware_blend(rrf_score, rerank_score, 0)
        
        # Rank 15: 40% RRF + 60% Rerank
        score_rank15 = position_aware_blend(rrf_score, rerank_score, 15)
        
        # 对于高 Rerank 分数，低排名应该产生更高的混合分数
        assert score_rank15 > score_rank0


class TestStrongSignal:
    """强信号检测测试。"""
    
    def _make_result(self, score: float) -> SearchResult:
        chunk = Chunk(
            doc_id="doc1",
            content="test",
            start_idx=0,
            end_idx=4,
            metadata={}
        )
        return SearchResult(chunk=chunk, score=score)
    
    def test_strong_signal_detected(self):
        """测试强信号被正确检测。"""
        results = [
            self._make_result(0.95),  # Top1 >= 0.85
            self._make_result(0.70),  # Gap = 0.25 >= 0.15
        ]
        
        signal = detect_strong_signal(results)
        
        assert signal.is_strong
        assert signal.top_score == 0.95
        assert signal.score_gap == 0.25
    
    def test_weak_signal_small_gap(self):
        """测试分数差太小不是强信号。"""
        results = [
            self._make_result(0.90),
            self._make_result(0.85),  # Gap = 0.05 < 0.15
        ]
        
        signal = detect_strong_signal(results)
        
        assert not signal.is_strong
    
    def test_weak_signal_low_top(self):
        """测试 Top1 分数不够高不是强信号。"""
        results = [
            self._make_result(0.70),  # < 0.85
            self._make_result(0.40),
        ]
        
        signal = detect_strong_signal(results)
        
        assert not signal.is_strong


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
