"""查询扩展 - 使用 LLM 生成查询变体以提升召回。

借鉴 QMD 项目的 Query Expansion 设计:
1. lex: 关键词变体 (用于 BM25)
2. vec: 语义句子 (用于 Vector)
3. hyde: 假设文档 (HyDE 技术)

Architecture alignment: L2 Agent Layer → Query Enhancement
"""

from dataclasses import dataclass, field
from typing import Any, Protocol
import re


@dataclass
class ExpandedQuery:
    """扩展后的查询。"""
    original: str           # 原始查询
    lex_variants: list[str] = field(default_factory=list)  # 关键词变体
    vec_variants: list[str] = field(default_factory=list)  # 语义句子
    hyde_doc: str | None = None  # 假设文档 (HyDE)
    
    def get_all_queries(self) -> list[str]:
        """获取所有查询变体（包含原始）。"""
        queries = [self.original]
        queries.extend(self.lex_variants)
        queries.extend(self.vec_variants)
        return queries
    
    def get_bm25_queries(self) -> list[str]:
        """获取用于 BM25 的查询。"""
        return [self.original] + self.lex_variants
    
    def get_vector_queries(self) -> list[str]:
        """获取用于 Vector 搜索的查询。"""
        queries = [self.original] + self.vec_variants
        if self.hyde_doc:
            queries.append(self.hyde_doc)
        return queries


class QueryExpanderProtocol(Protocol):
    """查询扩展器协议。"""
    
    def expand(self, query: str) -> ExpandedQuery:
        """扩展查询。"""
        ...


class LLMQueryExpander:
    """使用 LLM 进行查询扩展。
    
    生成三种类型的扩展:
    1. lex: 关键词同义词和变体
    2. vec: 更完整的语义句子
    3. hyde: 假设性答案文档
    
    Usage:
        expander = LLMQueryExpander(llm_client)
        expanded = expander.expand("how to reset password")
    """
    
    EXPANSION_PROMPT = """You are a search query expansion assistant. Given a user query, 
generate search variants to improve retrieval.

User Query: {query}

Generate the following (output EXACTLY in this format):
lex: <2-3 keyword variants separated by semicolons, for exact keyword matching>
vec: <1-2 semantic sentence variants, more descriptive versions of the query>
hyde: <A hypothetical 50-100 word document that would perfectly answer this query>

Example output:
lex: password recovery; forgot password; reset credentials
vec: How do I recover my account password if I forgot it?; Steps to reset my login password
hyde: To reset your password, navigate to the login page and click "Forgot Password". Enter your email address and you will receive a password reset link. Click the link within 24 hours to create a new password. Make sure your new password is at least 8 characters with mixed case and numbers.

Now generate for the given query:"""
    
    def __init__(
        self,
        llm_client: Any,
        max_lex_variants: int = 3,
        max_vec_variants: int = 2,
    ):
        """初始化查询扩展器。
        
        Args:
            llm_client: LLM 客户端
            max_lex_variants: 最大关键词变体数
            max_vec_variants: 最大语义变体数
        """
        self.llm_client = llm_client
        self.max_lex_variants = max_lex_variants
        self.max_vec_variants = max_vec_variants
    
    def expand(self, query: str) -> ExpandedQuery:
        """使用 LLM 扩展查询。
        
        Args:
            query: 原始用户查询
            
        Returns:
            ExpandedQuery 包含所有变体
        """
        prompt = self.EXPANSION_PROMPT.format(query=query)
        
        try:
            response = self.llm_client.chat(prompt)
            return self._parse_response(query, response)
        except Exception as e:
            # LLM 调用失败时返回原始查询
            return ExpandedQuery(original=query)
    
    def _parse_response(self, original: str, response: str) -> ExpandedQuery:
        """解析 LLM 响应。"""
        lex_variants = []
        vec_variants = []
        hyde_doc = None
        
        lines = response.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            
            if line.lower().startswith('lex:'):
                # 解析关键词变体
                content = line[4:].strip()
                variants = [v.strip() for v in content.split(';') if v.strip()]
                lex_variants = variants[:self.max_lex_variants]
                
            elif line.lower().startswith('vec:'):
                # 解析语义变体
                content = line[4:].strip()
                variants = [v.strip() for v in content.split(';') if v.strip()]
                vec_variants = variants[:self.max_vec_variants]
                
            elif line.lower().startswith('hyde:'):
                # 解析假设文档
                hyde_doc = line[5:].strip()
        
        # 如果 hyde 跨多行，尝试提取更多内容
        if hyde_doc and len(hyde_doc) < 50:
            # 可能 hyde 内容在后续行
            hyde_start = response.lower().find('hyde:')
            if hyde_start >= 0:
                hyde_content = response[hyde_start + 5:].strip()
                # 取第一个段落
                para_end = hyde_content.find('\n\n')
                if para_end > 0:
                    hyde_doc = hyde_content[:para_end].strip()
                else:
                    hyde_doc = hyde_content[:500].strip()  # 最多 500 字符
        
        return ExpandedQuery(
            original=original,
            lex_variants=lex_variants,
            vec_variants=vec_variants,
            hyde_doc=hyde_doc,
        )


class SimpleQueryExpander:
    """简单的查询扩展器 - 不使用 LLM。
    
    基于规则生成简单变体:
    - 同义词替换
    - 词序变化
    - 问句转陈述句
    """
    
    # 常见同义词映射
    SYNONYMS = {
        'create': ['make', 'build', 'generate'],
        'delete': ['remove', 'erase', 'clear'],
        'update': ['modify', 'change', 'edit'],
        'get': ['fetch', 'retrieve', 'obtain'],
        'add': ['insert', 'append', 'include'],
        'show': ['display', 'view', 'list'],
        'find': ['search', 'locate', 'discover'],
        'help': ['assist', 'guide', 'support'],
        'error': ['bug', 'issue', 'problem'],
        'fix': ['solve', 'repair', 'resolve'],
    }
    
    def expand(self, query: str) -> ExpandedQuery:
        """基于规则扩展查询。"""
        lex_variants = []
        
        # 生成同义词变体
        words = query.lower().split()
        for i, word in enumerate(words):
            if word in self.SYNONYMS:
                for syn in self.SYNONYMS[word][:2]:  # 每个词最多 2 个同义词
                    new_words = words.copy()
                    new_words[i] = syn
                    lex_variants.append(' '.join(new_words))
        
        # 移除问号变体
        if '?' in query:
            lex_variants.append(query.replace('?', '').strip())
        
        # 移除 "how to" 等前缀
        for prefix in ['how to ', 'how do i ', 'what is ', 'where is ']:
            if query.lower().startswith(prefix):
                lex_variants.append(query[len(prefix):].strip())
                break
        
        return ExpandedQuery(
            original=query,
            lex_variants=lex_variants[:3],  # 最多 3 个变体
        )


class NoOpExpander:
    """无操作扩展器 - 直接返回原始查询。"""
    
    def expand(self, query: str) -> ExpandedQuery:
        """返回未扩展的查询。"""
        return ExpandedQuery(original=query)
