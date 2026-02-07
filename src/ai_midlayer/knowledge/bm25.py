"""BM25 全文检索索引 - 基于 SQLite FTS5。

借鉴 QMD 项目的 FTS5 实现，提供高性能的关键词检索能力。
与 Vector 索引配合实现混合搜索。

Architecture alignment: L1 Infrastructure Layer → Full-Text Search
"""

import sqlite3
from pathlib import Path
from typing import Any

from ai_midlayer.knowledge.models import Document, Chunk, SearchResult


class BM25Index:
    """基于 SQLite FTS5 的 BM25 全文检索索引。
    
    使用 SQLite 内置的 FTS5 虚拟表实现高效的关键词搜索，
    支持 BM25 排序算法。
    
    Features:
    - Porter stemming (词干提取)
    - Unicode 支持
    - BM25 相关性打分
    - 增量更新
    
    Usage:
        index = BM25Index(".midlayer/bm25.db")
        index.index_document(doc)
        results = index.search("query terms", top_k=10)
    """
    
    def __init__(self, db_path: str | Path):
        """初始化 BM25 索引。
        
        Args:
            db_path: SQLite 数据库路径
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._init_database()
    
    def _init_database(self) -> None:
        """初始化数据库表结构。"""
        with sqlite3.connect(self.db_path) as conn:
            # 主文档表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    file_name TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            
            # Chunks 表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY,
                    doc_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    start_idx INTEGER NOT NULL,
                    end_idx INTEGER NOT NULL,
                    seq INTEGER NOT NULL,
                    FOREIGN KEY (doc_id) REFERENCES documents(id) ON DELETE CASCADE
                )
            """)
            
            # FTS5 虚拟表 - 全文检索
            # 使用 porter 词干提取 + unicode61 分词
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                    content,
                    file_name,
                    content_hash UNINDEXED,
                    chunk_id UNINDEXED,
                    doc_id UNINDEXED,
                    tokenize='porter unicode61'
                )
            """)
            
            # 创建索引
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON chunks(doc_id)
            """)
            
            conn.commit()
    
    def index_document(self, doc: Document) -> int:
        """索引一个文档。
        
        Args:
            doc: 要索引的文档
            
        Returns:
            索引的 chunk 数量
        """
        with sqlite3.connect(self.db_path) as conn:
            # 检查是否已存在 (基于内容 hash)
            existing = conn.execute(
                "SELECT id FROM documents WHERE id = ?",
                (doc.id,)
            ).fetchone()
            
            if existing:
                # 删除旧数据（触发 CASCADE 删除 chunks）
                self._remove_document_internal(conn, doc.id)
            
            # 插入文档
            import hashlib
            content_hash = hashlib.sha256(doc.content.encode()).hexdigest()[:16]
            
            from datetime import datetime
            conn.execute(
                """
                INSERT INTO documents (id, file_name, file_path, content_hash, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (doc.id, doc.file_name, doc.source_path, content_hash, datetime.now().isoformat())
            )
            
            # 分块并索引
            chunks = self._chunk_content(doc)
            
            for seq, chunk in enumerate(chunks):
                # 插入 chunk
                conn.execute(
                    """
                    INSERT INTO chunks (id, doc_id, content, start_idx, end_idx, seq)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (chunk.id, doc.id, chunk.content, chunk.start_idx, chunk.end_idx, seq)
                )
                
                # 插入 FTS5
                conn.execute(
                    """
                    INSERT INTO chunks_fts (content, file_name, content_hash, chunk_id, doc_id)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (chunk.content, doc.file_name, content_hash, chunk.id, doc.id)
                )
            
            conn.commit()
            return len(chunks)
    
    def _chunk_content(
        self,
        doc: Document,
        chunk_size: int = 800,
        overlap: int = 120
    ) -> list[Chunk]:
        """将文档内容分块。
        
        借鉴 QMD 的分块策略:
        - 800 字符一块
        - 15% 重叠 (约 120 字符)
        - 在段落/句子边界断开
        
        Args:
            doc: 文档
            chunk_size: 块大小（字符数）
            overlap: 重叠大小
            
        Returns:
            Chunk 列表
        """
        content = doc.content
        if len(content) <= chunk_size:
            return [Chunk(
                doc_id=doc.id,
                content=content,
                start_idx=0,
                end_idx=len(content),
                metadata={"file_name": doc.file_name, "seq": 0}
            )]
        
        chunks = []
        pos = 0
        seq = 0
        
        while pos < len(content):
            end_pos = min(pos + chunk_size, len(content))
            
            # 尝试在段落/句子边界断开
            if end_pos < len(content):
                search_start = int(len(content[pos:end_pos]) * 0.7)
                search_slice = content[pos + search_start:end_pos]
                
                break_offset = -1
                
                # 优先级: 段落 > 句子 > 换行 > 空格
                para_break = search_slice.rfind('\n\n')
                if para_break >= 0:
                    break_offset = para_break + 2
                else:
                    sentence_end = max(
                        search_slice.rfind('. '),
                        search_slice.rfind('.\n'),
                        search_slice.rfind('。'),
                        search_slice.rfind('？'),
                        search_slice.rfind('！'),
                    )
                    if sentence_end >= 0:
                        break_offset = sentence_end + 1
                    else:
                        line_break = search_slice.rfind('\n')
                        if line_break >= 0:
                            break_offset = line_break + 1
                        else:
                            space_break = search_slice.rfind(' ')
                            if space_break >= 0:
                                break_offset = space_break + 1
                
                if break_offset > 0:
                    end_pos = pos + search_start + break_offset
            
            chunk_content = content[pos:end_pos]
            chunks.append(Chunk(
                doc_id=doc.id,
                content=chunk_content,
                start_idx=pos,
                end_idx=end_pos,
                metadata={"file_name": doc.file_name, "seq": seq}
            ))
            
            seq += 1
            pos = end_pos - overlap if end_pos < len(content) else end_pos
        
        return chunks
    
    def search(self, query: str, top_k: int = 20) -> list[SearchResult]:
        """执行 BM25 搜索。
        
        Args:
            query: 搜索查询
            top_k: 返回结果数量
            
        Returns:
            SearchResult 列表，按相关性排序
        """
        fts_query = self._build_fts5_query(query)
        if not fts_query:
            return []
        
        with sqlite3.connect(self.db_path) as conn:
            # 使用 BM25 函数进行排序
            # bm25() 返回负值，值越小（绝对值越大）相关性越高
            results = conn.execute(
                """
                SELECT
                    f.chunk_id,
                    f.doc_id,
                    f.content,
                    f.file_name,
                    c.start_idx,
                    c.end_idx,
                    bm25(chunks_fts, 1.0, 0.5) as bm25_score
                FROM chunks_fts f
                JOIN chunks c ON c.id = f.chunk_id
                WHERE chunks_fts MATCH ?
                ORDER BY bm25_score ASC
                LIMIT ?
                """,
                (fts_query, top_k)
            ).fetchall()
            
            search_results = []
            for row in results:
                chunk_id, doc_id, content, file_name, start_idx, end_idx, bm25_score = row
                
                # 归一化分数: 将 BM25 负分转换为 0-1 范围
                # 借鉴 QMD: score = 1 / (1 + abs(bm25_score))
                score = 1.0 / (1.0 + abs(bm25_score))
                
                chunk = Chunk(
                    id=chunk_id,
                    doc_id=doc_id,
                    content=content,
                    start_idx=start_idx,
                    end_idx=end_idx,
                    metadata={"file_name": file_name, "source": "bm25"}
                )
                
                search_results.append(SearchResult(
                    chunk=chunk,
                    score=score
                ))
            
            return search_results
    
    def _build_fts5_query(self, query: str) -> str | None:
        """构建 FTS5 查询字符串。
        
        借鉴 QMD 的查询构建逻辑:
        - 每个词用引号包裹并加通配符
        - 多个词用 AND 连接
        
        Args:
            query: 原始查询
            
        Returns:
            FTS5 格式的查询字符串
        """
        # 分词并过滤
        import re
        terms = [t.strip() for t in re.split(r'\s+', query.strip()) if t.strip()]
        
        if not terms:
            return None
        
        # 转义特殊字符
        escaped_terms = []
        for term in terms:
            # 移除 FTS5 特殊字符
            clean_term = re.sub(r'["\'\*\(\)\[\]\{\}]', '', term)
            if clean_term:
                escaped_terms.append(clean_term)
        
        if not escaped_terms:
            return None
        
        if len(escaped_terms) == 1:
            return f'"{escaped_terms[0]}"*'
        
        return ' AND '.join(f'"{t}"*' for t in escaped_terms)
    
    def remove_document(self, doc_id: str) -> bool:
        """删除文档索引。
        
        Args:
            doc_id: 文档 ID
            
        Returns:
            是否成功删除
        """
        with sqlite3.connect(self.db_path) as conn:
            return self._remove_document_internal(conn, doc_id)
    
    def _remove_document_internal(self, conn: sqlite3.Connection, doc_id: str) -> bool:
        """内部删除方法。"""
        # 先删除 FTS 记录
        conn.execute("DELETE FROM chunks_fts WHERE doc_id = ?", (doc_id,))
        # 删除 chunks
        conn.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
        # 删除文档
        cursor = conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        conn.commit()
        return cursor.rowcount > 0
    
    def get_stats(self) -> dict[str, int]:
        """获取索引统计信息。"""
        with sqlite3.connect(self.db_path) as conn:
            doc_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            chunk_count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            return {
                "total_documents": doc_count,
                "total_chunks": chunk_count,
            }
    
    def clear(self) -> None:
        """清空索引。"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM chunks_fts")
            conn.execute("DELETE FROM chunks")
            conn.execute("DELETE FROM documents")
            conn.commit()
