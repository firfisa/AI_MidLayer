"""RRF 融合算法 - 倒数排名融合。

借鉴 QMD 项目的 RRF 实现，用于合并多路检索结果。

Reference: https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf
"""

from dataclasses import dataclass, field
from typing import TypeVar, Generic, Callable

from ai_midlayer.knowledge.models import SearchResult


@dataclass
class FusionResult:
    """融合后的结果。"""
    result: SearchResult
    rrf_score: float
    sources: list[str] = field(default_factory=list)
    is_top_rank: bool = False  # 是否在任一列表中排第一


def reciprocal_rank_fusion(
    result_lists: list[list[SearchResult]],
    weights: list[float] | None = None,
    k: int = 60,
    top_n: int = 30,
    top_rank_bonus: float = 0.05,
    top3_bonus: float = 0.02,
) -> list[FusionResult]:
    """执行倒数排名融合 (RRF)。
    
    将多个排名列表合并为一个统一的排名。
    
    公式: score = weight / (k + rank + 1)
    
    Args:
        result_lists: 多个检索结果列表
        weights: 每个列表的权重（默认全为 1.0）
        k: RRF 常数（通常为 60）
        top_n: 返回前 N 个结果
        top_rank_bonus: 排第一名的额外奖励
        top3_bonus: 排 2-3 名的额外奖励
        
    Returns:
        融合后的结果列表
    """
    if not result_lists:
        return []
    
    if weights is None:
        weights = [1.0] * len(result_lists)
    
    # 用 chunk_id 作为去重键
    scores: dict[str, FusionResult] = {}
    
    for list_idx, (results, weight) in enumerate(zip(result_lists, weights)):
        source_name = f"list_{list_idx}"
        
        for rank, result in enumerate(results):
            # 使用 chunk id 或生成唯一键
            key = result.chunk.id or f"{result.chunk.doc_id}_{result.chunk.start_idx}"
            
            if key not in scores:
                scores[key] = FusionResult(
                    result=result,
                    rrf_score=0.0,
                    sources=[],
                    is_top_rank=False,
                )
            
            # RRF 公式
            rrf_contribution = weight / (k + rank + 1)
            scores[key].rrf_score += rrf_contribution
            scores[key].sources.append(source_name)
            
            # 榜首奖励 (借鉴 QMD)
            if rank == 0:
                scores[key].rrf_score += top_rank_bonus
                scores[key].is_top_rank = True
            elif rank < 3:
                scores[key].rrf_score += top3_bonus
    
    # 按 RRF 分数降序排列
    sorted_results = sorted(
        scores.values(),
        key=lambda x: x.rrf_score,
        reverse=True
    )
    
    return sorted_results[:top_n]


def position_aware_blend(
    rrf_score: float,
    rerank_score: float,
    rrf_rank: int
) -> float:
    """位置感知混合 - 动态调整 RRF 和 Rerank 分数的权重。
    
    借鉴 QMD 的核心创新:
    - Top 1-3: 75% RRF + 25% Rerank (信任精确匹配)
    - Top 4-10: 60% RRF + 40% Rerank  
    - Top 11+: 40% RRF + 60% Rerank (信任语义理解)
    
    Args:
        rrf_score: RRF 融合分数
        rerank_score: LLM 重排序分数 (0-1)
        rrf_rank: 在 RRF 结果中的排名 (0-indexed)
        
    Returns:
        混合后的最终分数
    """
    if rrf_rank < 3:
        # Top 1-3: 信任关键词精确匹配
        rrf_weight = 0.75
    elif rrf_rank < 10:
        # Top 4-10: 平衡
        rrf_weight = 0.60
    else:
        # Top 11+: 更信任语义理解
        rrf_weight = 0.40
    
    rerank_weight = 1.0 - rrf_weight
    
    # 归一化 RRF 分数到 0-1 范围（假设最大 RRF 分数约为 0.5）
    normalized_rrf = min(rrf_score * 2.0, 1.0)
    
    return normalized_rrf * rrf_weight + rerank_score * rerank_weight


@dataclass
class StrongSignal:
    """强信号检测结果。"""
    is_strong: bool
    top_score: float
    score_gap: float


def detect_strong_signal(
    results: list[SearchResult],
    threshold: float = 0.85,
    gap_threshold: float = 0.15
) -> StrongSignal:
    """检测强信号 - 判断是否可以跳过查询扩展。
    
    借鉴 QMD 的优化策略:
    如果 Top1 分数 >= 0.85 且 (Top1 - Top2) >= 0.15，
    说明是精确匹配（如搜索文件名），可以跳过 LLM 扩展。
    
    Args:
        results: 初始 BM25 搜索结果
        threshold: Top1 分数阈值
        gap_threshold: Top1 与 Top2 的分数差阈值
        
    Returns:
        StrongSignal 检测结果
    """
    if len(results) < 2:
        return StrongSignal(
            is_strong=len(results) == 1 and results[0].score >= threshold,
            top_score=results[0].score if results else 0.0,
            score_gap=1.0 if len(results) == 1 else 0.0
        )
    
    top1_score = results[0].score
    top2_score = results[1].score
    score_gap = top1_score - top2_score
    
    is_strong = top1_score >= threshold and score_gap >= gap_threshold
    
    return StrongSignal(
        is_strong=is_strong,
        top_score=top1_score,
        score_gap=score_gap
    )
