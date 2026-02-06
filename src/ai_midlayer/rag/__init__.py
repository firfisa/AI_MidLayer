"""RAG 查询模块 - 检索增强生成。

实现 RAG 查询流程:
1. 检索相关文档
2. 构建上下文
3. LLM 生成回答

Architecture alignment: L2 Core Layer → RAG Query
"""

from dataclasses import dataclass, field
from typing import Any

from ai_midlayer.knowledge.retriever import Retriever
from ai_midlayer.knowledge.models import SearchResult
from ai_midlayer.llm import LiteLLMClient, LLMConfig, Message


@dataclass
class QueryResult:
    """RAG 查询结果。"""
    
    query: str
    answer: str
    sources: list[SearchResult] = field(default_factory=list)
    context_used: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    
    def format_sources(self) -> str:
        """格式化来源信息。"""
        if not self.sources:
            return "无相关来源"
        
        lines = []
        for i, src in enumerate(self.sources, 1):
            lines.append(f"{i}. {src.file_name} (相似度: {src.score:.2f})")
        return "\n".join(lines)


class RAGQuery:
    """RAG 查询引擎。
    
    流程:
    1. 使用 Retriever 检索相关文档
    2. 构建 Prompt (系统提示 + 上下文 + 用户问题)
    3. 调用 LLM 生成回答
    4. 返回结果和来源
    
    Usage:
        retriever = Retriever(store, index)
        llm_client = LiteLLMClient(config)
        
        rag = RAGQuery(retriever, llm_client)
        result = rag.query("什么是 Agent 架构?")
        
        print(result.answer)
        print(result.format_sources())
    """
    
    DEFAULT_SYSTEM_PROMPT = """你是一个知识助手，基于提供的上下文回答问题。

规则:
1. 只使用上下文中的信息回答问题
2. 如果上下文不包含答案，明确说明"根据提供的资料，无法回答这个问题"
3. 引用具体的信息来源
4. 保持回答简洁准确

上下文:
{context}"""
    
    def __init__(
        self,
        retriever: Retriever,
        llm_client: LiteLLMClient,
        system_prompt: str | None = None,
        top_k: int = 5,
        max_context_length: int = 4000,
    ):
        """初始化 RAG 查询引擎。
        
        Args:
            retriever: 文档检索器
            llm_client: LLM 客户端
            system_prompt: 自定义系统提示 (使用 {context} 占位符)
            top_k: 检索文档数量
            max_context_length: 最大上下文长度
        """
        self.retriever = retriever
        self.llm_client = llm_client
        self.system_prompt = system_prompt or self.DEFAULT_SYSTEM_PROMPT
        self.top_k = top_k
        self.max_context_length = max_context_length
    
    def query(self, question: str, top_k: int | None = None) -> QueryResult:
        """执行 RAG 查询。
        
        Args:
            question: 用户问题
            top_k: 可选，覆盖默认检索数量
            
        Returns:
            QueryResult 包含回答和来源
        """
        k = top_k or self.top_k
        
        # 1. 检索相关文档
        results = self.retriever.retrieve(question, top_k=k)
        
        # 2. 构建上下文
        context = self._build_context(results)
        
        # 3. 构建消息
        system = self.system_prompt.format(context=context)
        messages = [
            Message.system(system),
            Message.user(question),
        ]
        
        # 4. 调用 LLM
        response = self.llm_client.complete(messages)
        
        # 5. 返回结果
        return QueryResult(
            query=question,
            answer=response.content,
            sources=results,
            context_used=context,
            usage=response.usage,
        )
    
    def _build_context(self, results: list[SearchResult]) -> str:
        """构建上下文。"""
        if not results:
            return "没有找到相关文档。"
        
        context_parts = []
        total_length = 0
        
        for result in results:
            chunk_text = f"[来源: {result.file_name}]\n{result.content}"
            chunk_length = len(chunk_text)
            
            if total_length + chunk_length > self.max_context_length:
                # 截断
                remaining = self.max_context_length - total_length
                if remaining > 100:
                    context_parts.append(chunk_text[:remaining] + "...")
                break
            
            context_parts.append(chunk_text)
            total_length += chunk_length
        
        return "\n\n---\n\n".join(context_parts)
    
    async def aquery(self, question: str, top_k: int | None = None) -> QueryResult:
        """异步执行 RAG 查询。"""
        k = top_k or self.top_k
        
        # 1. 检索
        results = self.retriever.retrieve(question, top_k=k)
        
        # 2. 构建上下文
        context = self._build_context(results)
        
        # 3. 构建消息
        system = self.system_prompt.format(context=context)
        messages = [
            Message.system(system),
            Message.user(question),
        ]
        
        # 4. 异步调用 LLM
        response = await self.llm_client.acomplete(messages)
        
        # 5. 返回结果
        return QueryResult(
            query=question,
            answer=response.content,
            sources=results,
            context_used=context,
            usage=response.usage,
        )


class ConversationRAG:
    """多轮对话 RAG。
    
    支持对话历史和上下文累积。
    """
    
    def __init__(
        self,
        retriever: Retriever,
        llm_client: LiteLLMClient,
        max_history: int = 10,
    ):
        """初始化多轮对话 RAG。"""
        self.rag = RAGQuery(retriever, llm_client)
        self.history: list[tuple[str, str]] = []  # (question, answer)
        self.max_history = max_history
    
    def chat(self, question: str) -> QueryResult:
        """进行对话。"""
        # 执行查询
        result = self.rag.query(question)
        
        # 记录历史
        self.history.append((question, result.answer))
        
        # 限制历史长度
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
        
        return result
    
    def get_history(self) -> list[tuple[str, str]]:
        """获取对话历史。"""
        return self.history.copy()
    
    def clear_history(self) -> None:
        """清空对话历史。"""
        self.history.clear()
