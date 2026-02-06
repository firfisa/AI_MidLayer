"""文件解析 Agent - 重构版本。

继承 BaseAgent，实现 OODA + Reflexion 循环。
支持多种文件格式解析，输出结构化 Document 对象。

Architecture alignment: L3 Agent Layer → 文件解析 Agent
"""

from pathlib import Path
from typing import Any

from ai_midlayer.agents.base import BaseAgent
from ai_midlayer.agents.protocols import AgentPhase, AgentState, LLMProvider
from ai_midlayer.knowledge.models import Document


class ParserState(AgentState):
    """文件解析 Agent 的状态。"""
    
    # 输入
    file_path: str = ""
    
    # 解析结果
    parsed_document: Document | None = None
    
    # 解析策略
    parse_strategy: str = ""
    encoding: str = "utf-8"
    
    # 质量评估 (用于 Reflexion)
    quality_score: float = 0.0
    quality_issues: list[str] = []


class ParserAgent(BaseAgent[ParserState]):
    """文件解析 Agent。
    
    OODA 循环:
    - Observe: 检查文件是否存在，识别文件类型
    - Orient: 确定解析策略
    - Decide: 选择解析方法
    - Act: 执行解析
    
    Reflexion:
    - Reflect: 评估解析质量
    - Refine: 如果质量不佳，尝试其他策略
    
    Usage:
        agent = ParserAgent()
        doc = agent.run("/path/to/file.md")
    """
    
    # 支持的文件类型
    TEXT_TYPES = {"md", "txt", "json", "py", "yml", "yaml", "toml", "ini", "cfg", "js", "ts", "html", "css"}
    BINARY_TYPES = {"pdf", "docx", "xlsx", "pptx"}
    
    def __init__(
        self,
        max_iterations: int = 2,
        llm: LLMProvider | None = None,
    ):
        """初始化解析 Agent。
        
        Args:
            max_iterations: 最大迭代次数
            llm: 可选的 LLM Provider (用于高级解析)
        """
        super().__init__(max_iterations=max_iterations, llm=llm)
    
    def create_state(self, input_data: Any) -> ParserState:
        """创建初始状态。"""
        return ParserState(
            input=input_data,
            file_path=str(input_data),
            max_iterations=self.max_iterations,
        )
    
    def observe(self, state: ParserState) -> dict[str, Any]:
        """观察文件状态。"""
        path = Path(state.file_path)
        
        observation = {
            "path": str(path),
            "exists": path.exists(),
            "is_file": path.is_file() if path.exists() else False,
            "file_type": path.suffix.lstrip(".").lower() if path.exists() else None,
            "size_bytes": path.stat().st_size if path.exists() and path.is_file() else 0,
            "file_name": path.name if path.exists() else None,
        }
        
        return observation
    
    def orient(self, state: ParserState, observation: dict[str, Any]) -> dict[str, Any]:
        """分析解析策略。"""
        if not observation["exists"]:
            return {"error": "File not found", "strategy": None}
        
        if not observation["is_file"]:
            return {"error": "Path is not a file", "strategy": None}
        
        file_type = observation["file_type"]
        
        if file_type in self.TEXT_TYPES:
            return {
                "strategy": "text",
                "encoding": "utf-8",
                "parser": "native",
            }
        elif file_type in self.BINARY_TYPES:
            return {
                "strategy": "binary",
                "parser": "unstructured",  # TODO: 集成 Unstructured.io
                "warning": "Binary parsing is basic, will improve in Phase 1 enhancement",
            }
        else:
            return {
                "strategy": "fallback",
                "parser": "raw_bytes",
                "warning": f"Unknown file type: {file_type}",
            }
    
    def decide(self, state: ParserState, orientation: dict[str, Any]) -> dict[str, Any]:
        """决定解析动作。"""
        if "error" in orientation:
            return {"action": "abort", "reason": orientation["error"]}
        
        state.parse_strategy = orientation["strategy"]
        
        return {
            "action": "parse",
            "strategy": orientation["strategy"],
            "parser": orientation["parser"],
        }
    
    def act(self, state: ParserState, decision: dict[str, Any]) -> dict[str, Any]:
        """执行解析。"""
        if decision["action"] == "abort":
            state.is_complete = True
            state.output = None
            return {"success": False, "error": decision["reason"]}
        
        try:
            # 创建文档
            doc = Document.from_file(state.file_path)
            state.parsed_document = doc
            state.output = doc
            
            # 评估质量
            state.quality_score = self._evaluate_quality(doc)
            
            return {
                "success": True,
                "doc_id": doc.id,
                "content_length": len(doc.content),
                "quality_score": state.quality_score,
            }
            
        except Exception as e:
            state.add_error(str(e))
            return {"success": False, "error": str(e)}
    
    def reflect(self, state: ParserState, action_result: dict[str, Any]) -> str:
        """反思解析质量。"""
        if not action_result.get("success"):
            return f"Parsing failed: {action_result.get('error')}. Need to try alternative approach."
        
        quality = state.quality_score
        
        if quality < 0.3:
            state.quality_issues.append("Very low content quality")
            return "Content quality is very low, may need OCR or different parser."
        elif quality < 0.6:
            state.quality_issues.append("Medium content quality")
            return "Content quality is medium, might benefit from enhanced parsing."
        else:
            return "Content quality is good, parsing complete."
    
    def should_refine(self, state: ParserState, reflection: str) -> bool:
        """判断是否需要重新解析。"""
        # 如果有 LLM，且质量低，可以尝试增强解析
        if self.llm and state.quality_score < 0.3:
            return True
        
        # 如果已经尝试过，不再重试
        if state.iteration > 0:
            return False
        
        return "need" in reflection.lower() or "failed" in reflection.lower()
    
    def finalize(self, state: ParserState) -> Document | None:
        """返回解析后的文档。"""
        if state.parsed_document:
            # 添加解析元数据
            state.parsed_document.metadata["parse_strategy"] = state.parse_strategy
            state.parsed_document.metadata["quality_score"] = state.quality_score
            state.parsed_document.metadata["quality_issues"] = state.quality_issues
        
        return state.parsed_document
    
    def _evaluate_quality(self, doc: Document) -> float:
        """评估文档解析质量 (0-1)。"""
        if not doc.content:
            return 0.0
        
        content = doc.content
        
        # 简单启发式评估
        score = 1.0
        
        # 内容太短扣分
        if len(content) < 100:
            score -= 0.3
        
        # 乱码检测 (高比例非 ASCII)
        non_ascii_ratio = sum(1 for c in content if ord(c) > 127) / len(content)
        if non_ascii_ratio > 0.5:
            score -= 0.2  # 可能是中文，不一定是乱码
        
        # 检测常见解析错误模式
        if "\\x" in content or "\\u" in content:
            score -= 0.3
        
        return max(0.0, min(1.0, score))
    
    def parse(self, path: str | Path) -> Document | None:
        """便捷方法：解析单个文件。
        
        Args:
            path: 文件路径
            
        Returns:
            解析后的 Document，或 None 如果失败
        """
        return self.run(str(path))
