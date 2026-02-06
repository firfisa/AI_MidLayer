"""结构识别 Agent - 识别文档内部结构和类型。

继承 BaseAgent，实现 OODA + Reflexion 循环。
识别文档的层级结构、章节划分、文档类型。

Architecture alignment: L3 Agent Layer → 结构识别 Agent
"""

from enum import Enum
from typing import Any

from pydantic import Field

from ai_midlayer.agents.base import BaseAgent
from ai_midlayer.agents.protocols import AgentState, LLMProvider
from ai_midlayer.knowledge.models import Document


class DocumentType(str, Enum):
    """文档类型分类。"""
    
    TECHNICAL_DOC = "technical_doc"      # 技术文档
    MEETING_NOTES = "meeting_notes"      # 会议记录
    REQUIREMENT = "requirement"          # 需求文档
    DESIGN_DOC = "design_doc"            # 设计文档
    RESEARCH = "research"                # 研究报告
    CODE = "code"                        # 代码文件
    CONFIG = "config"                    # 配置文件
    DATA = "data"                        # 数据文件
    GENERAL = "general"                  # 通用文档
    UNKNOWN = "unknown"                  # 未知


class StructureNode:
    """文档结构节点。"""
    
    def __init__(
        self,
        title: str,
        level: int,
        content: str = "",
        start_idx: int = 0,
        end_idx: int = 0,
        node_type: str = "section",
    ):
        self.title = title
        self.level = level
        self.content = content
        self.start_idx = start_idx
        self.end_idx = end_idx
        self.node_type = node_type
        self.children: list["StructureNode"] = []
    
    def add_child(self, node: "StructureNode") -> None:
        """添加子节点。"""
        self.children.append(node)
    
    def to_dict(self) -> dict:
        """转换为字典。"""
        return {
            "title": self.title,
            "level": self.level,
            "content_preview": self.content[:100] if self.content else "",
            "node_type": self.node_type,
            "children": [c.to_dict() for c in self.children],
        }


class DocumentStructure:
    """文档结构表示。"""
    
    def __init__(self, doc_id: str):
        self.doc_id = doc_id
        self.doc_type: DocumentType = DocumentType.UNKNOWN
        self.root: StructureNode = StructureNode("root", 0)
        self.sections: list[StructureNode] = []
        self.tags: list[str] = []
        self.summary: str = ""
    
    def to_dict(self) -> dict:
        """转换为字典。"""
        return {
            "doc_id": self.doc_id,
            "doc_type": self.doc_type.value,
            "structure": self.root.to_dict(),
            "section_count": len(self.sections),
            "tags": self.tags,
            "summary": self.summary,
        }


class StructureState(AgentState):
    """结构识别 Agent 的状态。"""
    
    model_config = {"arbitrary_types_allowed": True}
    
    # 输入文档
    document: Document | None = None
    
    # 识别结果
    structure: DocumentStructure | None = None
    
    # 识别过程
    detected_patterns: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class StructureAgent(BaseAgent[StructureState]):
    """结构识别 Agent。
    
    OODA 循环:
    - Observe: 分析文档内容特征
    - Orient: 识别文档类型和结构模式
    - Decide: 确定结构解析策略
    - Act: 构建结构树
    
    Reflexion:
    - Reflect: 评估结构识别的完整性
    - Refine: 如果识别不完整，尝试深度分析
    
    Usage:
        agent = StructureAgent()
        structure = agent.run(document)
    """
    
    # 文档类型特征关键词
    TYPE_PATTERNS = {
        DocumentType.TECHNICAL_DOC: ["api", "implementation", "function", "class", "method", "架构", "接口"],
        DocumentType.MEETING_NOTES: ["会议", "meeting", "议程", "agenda", "与会", "决议", "action"],
        DocumentType.REQUIREMENT: ["需求", "requirement", "功能", "feature", "用户故事", "user story"],
        DocumentType.DESIGN_DOC: ["设计", "design", "方案", "流程", "架构图", "diagram"],
        DocumentType.RESEARCH: ["研究", "research", "分析", "调研", "报告", "conclusion"],
        DocumentType.CODE: ["def ", "class ", "import ", "function", "const ", "let "],
        DocumentType.CONFIG: ["[", "]", "=", ":", "{", "}", "yaml", "json", "toml"],
    }
    
    # Markdown 标题模式
    HEADING_PATTERNS = [
        (r"^#{1}\s+(.+)$", 1),
        (r"^#{2}\s+(.+)$", 2),
        (r"^#{3}\s+(.+)$", 3),
        (r"^#{4}\s+(.+)$", 4),
        (r"^#{5}\s+(.+)$", 5),
        (r"^#{6}\s+(.+)$", 6),
    ]
    
    def __init__(
        self,
        max_iterations: int = 2,
        llm: LLMProvider | None = None,
    ):
        """初始化结构识别 Agent。"""
        super().__init__(max_iterations=max_iterations, llm=llm)
    
    def create_state(self, input_data: Any) -> StructureState:
        """创建初始状态。"""
        if isinstance(input_data, Document):
            return StructureState(
                input=input_data,
                document=input_data,
                max_iterations=self.max_iterations,
            )
        else:
            raise ValueError("StructureAgent requires a Document as input")
    
    def observe(self, state: StructureState) -> dict[str, Any]:
        """观察文档特征。"""
        doc = state.document
        if not doc or not doc.content:
            return {"error": "No document content", "features": {}}
        
        content = doc.content
        
        # 提取特征
        features = {
            "file_type": doc.file_type,
            "content_length": len(content),
            "line_count": content.count("\n") + 1,
            "has_headings": "#" in content or content.count("\n\n") > 3,
            "has_code_blocks": "```" in content,
            "has_lists": any(c in content for c in ["- ", "* ", "1. "]),
            "has_tables": "|" in content and "-|-" in content,
        }
        
        # 检测文档类型关键词
        type_scores = {}
        content_lower = content.lower()
        for doc_type, patterns in self.TYPE_PATTERNS.items():
            score = sum(1 for p in patterns if p.lower() in content_lower)
            if score > 0:
                type_scores[doc_type.value] = score
        
        features["type_scores"] = type_scores
        
        return {"features": features}
    
    def orient(self, state: StructureState, observation: dict[str, Any]) -> dict[str, Any]:
        """确定文档类型和解析策略。"""
        if "error" in observation:
            return {"error": observation["error"]}
        
        features = observation["features"]
        type_scores = features.get("type_scores", {})
        
        # 确定文档类型
        if type_scores:
            best_type = max(type_scores, key=type_scores.get)
            doc_type = DocumentType(best_type)
            confidence = min(1.0, type_scores[best_type] / 5)
        else:
            doc_type = DocumentType.GENERAL
            confidence = 0.5
        
        # 确定解析策略
        if features.get("file_type") in ["md", "markdown"]:
            strategy = "markdown"
        elif features.get("file_type") in ["py", "js", "ts"]:
            strategy = "code"
        else:
            strategy = "text"
        
        state.detected_patterns = list(type_scores.keys())
        state.confidence = confidence
        
        return {
            "doc_type": doc_type,
            "strategy": strategy,
            "confidence": confidence,
        }
    
    def decide(self, state: StructureState, orientation: dict[str, Any]) -> dict[str, Any]:
        """决定结构解析动作。"""
        if "error" in orientation:
            return {"action": "abort", "reason": orientation["error"]}
        
        return {
            "action": "parse_structure",
            "doc_type": orientation["doc_type"],
            "strategy": orientation["strategy"],
        }
    
    def act(self, state: StructureState, decision: dict[str, Any]) -> dict[str, Any]:
        """执行结构解析。"""
        if decision["action"] == "abort":
            state.is_complete = True
            return {"success": False, "error": decision["reason"]}
        
        doc = state.document
        strategy = decision["strategy"]
        doc_type = decision["doc_type"]
        
        # 创建结构对象
        structure = DocumentStructure(doc.id)
        structure.doc_type = doc_type
        
        # 解析结构
        if strategy == "markdown":
            self._parse_markdown_structure(doc.content, structure)
        elif strategy == "code":
            self._parse_code_structure(doc.content, structure)
        else:
            self._parse_text_structure(doc.content, structure)
        
        # 生成标签
        structure.tags = self._generate_tags(doc, doc_type)
        
        # 生成摘要 (简单版本)
        structure.summary = self._generate_summary(doc, structure)
        
        state.structure = structure
        state.output = structure
        
        return {
            "success": True,
            "section_count": len(structure.sections),
            "doc_type": doc_type.value,
        }
    
    def reflect(self, state: StructureState, action_result: dict[str, Any]) -> str:
        """反思结构识别质量。"""
        if not action_result.get("success"):
            return f"Structure parsing failed: {action_result.get('error')}"
        
        section_count = action_result.get("section_count", 0)
        confidence = state.confidence
        
        if section_count == 0:
            return "No sections detected, document may be unstructured. Need deeper analysis."
        
        if confidence < 0.3:
            return "Low confidence in document type classification. May need LLM assistance."
        
        return "Structure recognition complete with acceptable confidence."
    
    def finalize(self, state: StructureState) -> DocumentStructure | None:
        """返回结构识别结果。"""
        return state.structure
    
    def _parse_markdown_structure(self, content: str, structure: DocumentStructure) -> None:
        """解析 Markdown 结构。"""
        import re
        
        lines = content.split("\n")
        current_section = None
        section_content = []
        section_start = 0
        
        for i, line in enumerate(lines):
            # 检测标题
            heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
            
            if heading_match:
                # 保存之前的 section
                if current_section:
                    current_section.content = "\n".join(section_content)
                    current_section.end_idx = sum(len(l) + 1 for l in lines[:i])
                
                # 创建新 section
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                
                current_section = StructureNode(
                    title=title,
                    level=level,
                    start_idx=sum(len(l) + 1 for l in lines[:i]),
                    node_type="heading",
                )
                structure.sections.append(current_section)
                section_content = []
                section_start = i + 1
            else:
                section_content.append(line)
        
        # 保存最后一个 section
        if current_section:
            current_section.content = "\n".join(section_content)
            current_section.end_idx = len(content)
    
    def _parse_code_structure(self, content: str, structure: DocumentStructure) -> None:
        """解析代码结构（简单版本）。"""
        import re
        
        # 检测函数和类定义
        patterns = [
            (r"^def\s+(\w+)\s*\(", "function"),
            (r"^class\s+(\w+)", "class"),
            (r"^async\s+def\s+(\w+)", "async_function"),
        ]
        
        for line_num, line in enumerate(content.split("\n")):
            for pattern, node_type in patterns:
                match = re.match(pattern, line.strip())
                if match:
                    node = StructureNode(
                        title=match.group(1),
                        level=1,
                        node_type=node_type,
                    )
                    structure.sections.append(node)
    
    def _parse_text_structure(self, content: str, structure: DocumentStructure) -> None:
        """解析普通文本结构。"""
        # 按空行分段
        paragraphs = content.split("\n\n")
        
        for i, para in enumerate(paragraphs):
            if para.strip():
                node = StructureNode(
                    title=f"Paragraph {i + 1}",
                    level=1,
                    content=para.strip(),
                    node_type="paragraph",
                )
                structure.sections.append(node)
    
    def _generate_tags(self, doc: Document, doc_type: DocumentType) -> list[str]:
        """生成文档标签。"""
        tags = [doc_type.value, doc.file_type]
        
        content_lower = doc.content.lower()
        
        # 添加技术相关标签
        tech_keywords = {
            "python": ["python", ".py", "def ", "import "],
            "api": ["api", "endpoint", "rest", "http"],
            "database": ["database", "sql", "query", "table"],
            "ai": ["ai", "machine learning", "model", "neural"],
        }
        
        for tag, keywords in tech_keywords.items():
            if any(kw in content_lower for kw in keywords):
                tags.append(tag)
        
        return list(set(tags))
    
    def _generate_summary(self, doc: Document, structure: DocumentStructure) -> str:
        """生成文档摘要（简单版本）。"""
        # 取前几行作为摘要
        lines = doc.content.split("\n")[:5]
        summary_lines = [l.strip() for l in lines if l.strip() and not l.startswith("#")]
        
        if summary_lines:
            return " ".join(summary_lines)[:200]
        elif structure.sections:
            return f"Document with {len(structure.sections)} sections"
        else:
            return "Unstructured document"
    
    def analyze(self, doc: Document) -> DocumentStructure | None:
        """便捷方法：分析文档结构。
        
        Args:
            doc: 要分析的文档
            
        Returns:
            文档结构，或 None 如果失败
        """
        return self.run(doc)
