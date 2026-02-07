"""LLM 重排序器 - 使用 LLM 对检索结果进行精确打分。

借鉴 QMD 项目的 Reranker 设计:
1. Cross-encoder 式的精确打分
2. 使用 Yes/No 判断 + logprobs
3. 位置感知混合

Architecture alignment: L2 Agent Layer → LLM Reranking
"""

from dataclasses import dataclass
from typing import Protocol, Any

from ai_midlayer.knowledge.models import SearchResult, Chunk
from ai_midlayer.rag.fusion import position_aware_blend, FusionResult


# Reranker 协议 - 支持不同的重排序实现
class RerankerProtocol(Protocol):
    """重排序器协议。"""
    
    def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int = 10
    ) -> list[SearchResult]:
        """对结果进行重排序。"""
        ...


@dataclass
class RerankResult:
    """重排序结果。"""
    result: SearchResult
    rerank_score: float  # LLM 重排序分数 (0-1)
    original_rank: int   # 原始排名
    final_score: float   # 最终混合分数


class LLMReranker:
    """使用 LLM 进行精确重排序。
    
    Cross-encoder 逻辑:
    1. 构造 (query, document) 对
    2. LLM 判断相关性
    3. 解析分数 (0-1)
    4. 与 RRF 分数混合
    
    Usage:
        reranker = LLMReranker(llm_client)
        reranked = reranker.rerank(query, results)
    """
    
    # 重排序 Prompt 模板
    RERANK_PROMPT = """You are a relevance scoring assistant. Given a query and a document, 
rate how relevant the document is to answering the query.

Query: {query}

Document:
{document}

Rate the relevance on a scale of 0.0 to 1.0, where:
- 0.0 = completely irrelevant
- 0.5 = somewhat relevant
- 1.0 = highly relevant and directly answers the query

Respond with ONLY a number between 0.0 and 1.0, nothing else."""
    
    def __init__(
        self,
        llm_client: Any,
        max_doc_length: int = 1000,
        use_position_blend: bool = True,
    ):
        """初始化重排序器。
        
        Args:
            llm_client: LLM 客户端 (LiteLLMClient)
            max_doc_length: 文档最大长度（截断）
            use_position_blend: 是否使用位置感知混合
        """
        self.llm_client = llm_client
        self.max_doc_length = max_doc_length
        self.use_position_blend = use_position_blend
    
    def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int = 10,
    ) -> list[SearchResult]:
        """对结果进行重排序。
        
        Args:
            query: 搜索查询
            results: 原始搜索结果（按 RRF/similarity 排序）
            top_k: 返回前 K 个结果
            
        Returns:
            重排序后的 SearchResult 列表
        """
        if not results:
            return []
        
        # 只对前 N 个结果进行重排序（节省 LLM 调用）
        candidates = results[:min(len(results), top_k * 2)]
        
        # 为每个候选文档打分
        rerank_results: list[RerankResult] = []
        
        for idx, result in enumerate(candidates):
            rerank_score = self._score_document(query, result)
            
            # 计算最终分数
            if self.use_position_blend:
                final_score = position_aware_blend(
                    rrf_score=result.score,
                    rerank_score=rerank_score,
                    rrf_rank=idx
                )
            else:
                # 简单混合: 50% RRF + 50% Rerank
                final_score = result.score * 0.5 + rerank_score * 0.5
            
            rerank_results.append(RerankResult(
                result=result,
                rerank_score=rerank_score,
                original_rank=idx,
                final_score=final_score,
            ))
        
        # 按最终分数排序
        rerank_results.sort(key=lambda x: x.final_score, reverse=True)
        
        # 更新 SearchResult 的分数并返回
        final_results = []
        for rr in rerank_results[:top_k]:
            # 创建新的 SearchResult，保留原始 chunk 但更新分数
            new_result = SearchResult(
                chunk=rr.result.chunk,
                score=rr.final_score,
            )
            final_results.append(new_result)
        
        return final_results
    
    def _score_document(self, query: str, result: SearchResult) -> float:
        """使用 LLM 为单个文档打分。
        
        Returns:
            0.0 到 1.0 的相关性分数
        """
        # 截断文档内容
        doc_content = result.chunk.content[:self.max_doc_length]
        if len(result.chunk.content) > self.max_doc_length:
            doc_content += "..."
        
        prompt = self.RERANK_PROMPT.format(
            query=query,
            document=doc_content,
        )
        
        try:
            response = self.llm_client.chat(prompt)
            
            # 解析分数
            score = self._parse_score(response)
            return score
            
        except Exception as e:
            # 如果 LLM 调用失败，返回原始分数
            return result.score
    
    def _parse_score(self, response: str) -> float:
        """解析 LLM 返回的分数。"""
        try:
            # 提取数字
            import re
            match = re.search(r'(\d+\.?\d*)', response.strip())
            if match:
                score = float(match.group(1))
                # 确保在 0-1 范围内
                return max(0.0, min(1.0, score))
        except (ValueError, AttributeError):
            pass
        
        # 解析失败，返回中等分数
        return 0.5
    
    def rerank_with_details(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int = 10,
    ) -> list[RerankResult]:
        """重排序并返回详细信息。
        
        用于调试和分析。
        """
        if not results:
            return []
        
        candidates = results[:min(len(results), top_k * 2)]
        rerank_results: list[RerankResult] = []
        
        for idx, result in enumerate(candidates):
            rerank_score = self._score_document(query, result)
            
            if self.use_position_blend:
                final_score = position_aware_blend(
                    rrf_score=result.score,
                    rerank_score=rerank_score,
                    rrf_rank=idx
                )
            else:
                final_score = result.score * 0.5 + rerank_score * 0.5
            
            rerank_results.append(RerankResult(
                result=result,
                rerank_score=rerank_score,
                original_rank=idx,
                final_score=final_score,
            ))
        
        rerank_results.sort(key=lambda x: x.final_score, reverse=True)
        return rerank_results[:top_k]


class NoOpReranker:
    """无操作重排序器 - 直接返回原始结果。
    
    用于不需要 LLM 重排序的场景。
    """
    
    def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int = 10
    ) -> list[SearchResult]:
        """直接返回原始结果（不做任何处理）。"""
        return results[:top_k]


class ScoreBasedReranker:
    """基于简单规则的重排序器。
    
    不使用 LLM，而是根据文档特征进行打分:
    - 标题匹配加分
    - 关键词密度
    - 文档长度惩罚
    """
    
    def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int = 10
    ) -> list[SearchResult]:
        """基于规则重排序。"""
        scored_results = []
        query_terms = set(query.lower().split())
        
        for result in results:
            score = result.score
            content = result.chunk.content.lower()
            
            # 关键词密度加成
            term_count = sum(1 for term in query_terms if term in content)
            density_bonus = term_count * 0.05
            
            # 文档长度惩罚 (太短或太长都减分)
            length = len(result.chunk.content)
            if length < 100:
                length_penalty = 0.1
            elif length > 2000:
                length_penalty = 0.05
            else:
                length_penalty = 0
            
            # 计算最终分数
            final_score = score + density_bonus - length_penalty
            
            # 创建新结果
            new_result = SearchResult(
                chunk=result.chunk,
                score=max(0.0, min(1.0, final_score)),
            )
            scored_results.append(new_result)
        
        # 按分数排序
        scored_results.sort(key=lambda x: x.score, reverse=True)
        return scored_results[:top_k]
