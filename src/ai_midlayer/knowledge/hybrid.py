"""混合检索器 - 结合 Vector 和 BM25 搜索。

借鉴 QMD 项目的混合搜索架构:
1. BM25 (关键词精确匹配)
2. Vector (语义相似度)
3. RRF 融合 (倒数排名融合)
4. 可选的 LLM 重排序

Architecture alignment: L1 Infrastructure Layer → Hybrid Retrieval
"""

from pathlib import Path
from typing import Protocol, Any

from ai_midlayer.knowledge.models import SearchResult, Document
from ai_midlayer.knowledge.bm25 import BM25Index
from ai_midlayer.knowledge.index import VectorIndex
from ai_midlayer.knowledge.store import FileStore
from ai_midlayer.rag.fusion import (
    reciprocal_rank_fusion,
    position_aware_blend,
    detect_strong_signal,
    FusionResult,
    StrongSignal,
)


class HybridRetriever:
    """混合检索器 - 结合 BM25 和 Vector 搜索。
    
    Pipeline:
    1. 并行执行 BM25 和 Vector 搜索
    2. 使用 RRF 融合结果
    3. 可选: 检测强信号跳过扩展
    4. 可选: LLM 重排序
    
    Usage:
        retriever = HybridRetriever(kb_path)
        results = retriever.search("query", top_k=10)
    """
    
    def __init__(
        self,
        store: FileStore,
        vector_index: VectorIndex,
        bm25_index: BM25Index | None = None
    ):
        """初始化混合检索器。
        
        Args:
            store: 文件存储
            vector_index: 向量索引
            bm25_index: BM25 索引（可选，如果不提供则仅用向量搜索）
        """
        self.store = store
        self.vector_index = vector_index
        self.bm25_index = bm25_index
        
        # 配置
        self.vector_weight = 1.0  # 向量搜索权重
        self.bm25_weight = 2.0    # BM25 权重 (借鉴 QMD: 原查询权重 x2)
        self.enable_strong_signal = True
    
    @classmethod
    def from_path(cls, kb_path: str | Path) -> "HybridRetriever":
        """从知识库路径创建检索器。
        
        Args:
            kb_path: 知识库路径
            
        Returns:
            HybridRetriever 实例
        """
        kb_path = Path(kb_path)
        store = FileStore(kb_path)
        vector_index = VectorIndex(kb_path)
        
        # 创建 BM25 索引
        bm25_db_path = kb_path / "index" / "bm25.db"
        bm25_index = BM25Index(bm25_db_path)
        
        return cls(store, vector_index, bm25_index)
    
    def search(
        self,
        query: str,
        top_k: int = 10,
        use_hybrid: bool = True,
    ) -> list[SearchResult]:
        """执行混合搜索。
        
        Args:
            query: 搜索查询
            top_k: 返回结果数量
            use_hybrid: 是否使用混合搜索（False 则仅用向量搜索）
            
        Returns:
            SearchResult 列表
        """
        if not use_hybrid or self.bm25_index is None:
            # 仅向量搜索
            return self.vector_index.search(query, top_k=top_k)
        
        # 并行搜索 (在 Python 中顺序执行，但可以用 asyncio 优化)
        vector_results = self.vector_index.search(query, top_k=top_k * 2)
        bm25_results = self.bm25_index.search(query, top_k=top_k * 2)
        
        # 检测强信号
        if self.enable_strong_signal:
            signal = detect_strong_signal(bm25_results)
            if signal.is_strong:
                # 强信号: 直接返回 BM25 结果，跳过融合
                return bm25_results[:top_k]
        
        # RRF 融合
        fusion_results = reciprocal_rank_fusion(
            result_lists=[bm25_results, vector_results],
            weights=[self.bm25_weight, self.vector_weight],
            top_n=top_k,
        )
        
        # 提取 SearchResult
        return [fr.result for fr in fusion_results]
    
    def search_with_fusion_info(
        self,
        query: str,
        top_k: int = 10,
    ) -> tuple[list[FusionResult], StrongSignal | None]:
        """执行搜索并返回融合信息。
        
        用于调试和分析搜索过程。
        
        Returns:
            (融合结果列表, 强信号检测结果)
        """
        if self.bm25_index is None:
            vector_results = self.vector_index.search(query, top_k=top_k)
            fusion_results = [
                FusionResult(result=r, rrf_score=r.score, sources=["vector"])
                for r in vector_results
            ]
            return fusion_results, None
        
        vector_results = self.vector_index.search(query, top_k=top_k * 2)
        bm25_results = self.bm25_index.search(query, top_k=top_k * 2)
        
        signal = detect_strong_signal(bm25_results)
        
        if signal.is_strong:
            fusion_results = [
                FusionResult(result=r, rrf_score=r.score, sources=["bm25"], is_top_rank=i==0)
                for i, r in enumerate(bm25_results[:top_k])
            ]
            return fusion_results, signal
        
        fusion_results = reciprocal_rank_fusion(
            result_lists=[bm25_results, vector_results],
            weights=[self.bm25_weight, self.vector_weight],
            top_n=top_k,
        )
        
        return fusion_results, signal
    
    def index_document(self, doc: Document) -> dict[str, int]:
        """索引文档到所有索引。
        
        Args:
            doc: 要索引的文档
            
        Returns:
            各索引的 chunk 数量
        """
        result = {}
        
        # 向量索引
        vector_chunks = self.vector_index.index_document(doc)
        result["vector"] = vector_chunks
        
        # BM25 索引
        if self.bm25_index:
            bm25_chunks = self.bm25_index.index_document(doc)
            result["bm25"] = bm25_chunks
        
        return result
    
    def remove_document(self, doc_id: str) -> None:
        """从所有索引删除文档。"""
        self.vector_index.remove_document(doc_id)
        if self.bm25_index:
            self.bm25_index.remove_document(doc_id)
    
    def get_stats(self) -> dict[str, Any]:
        """获取索引统计信息。"""
        stats = {
            "vector": self.vector_index.get_stats(),
        }
        if self.bm25_index:
            stats["bm25"] = self.bm25_index.get_stats()
        return stats


def get_hybrid_retriever(kb_path: str | Path | None = None) -> HybridRetriever:
    """获取混合检索器的便捷函数。
    
    Args:
        kb_path: 知识库路径，默认使用当前目录
        
    Returns:
        HybridRetriever 实例
    """
    if kb_path is None:
        kb_path = Path.cwd() / ".midlayer"
    return HybridRetriever.from_path(kb_path)
