"""编排层 - 协调多个 Agent 的工作流。

遵循高内聚低耦合原则：
- 编排逻辑与 Agent 实现分离
- 通过接口通信，不依赖具体实现
- 支持流水线、并行、条件分支等模式

Architecture alignment: L4 Orchestrator Layer
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Callable, Generic, TypeVar

from pydantic import BaseModel, Field

from ai_midlayer.agents.protocols import AgentProtocol, AgentState


# ============================================================
# Pipeline Models
# ============================================================

class StepStatus(str, Enum):
    """步骤执行状态。"""
    
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PipelineStep(BaseModel):
    """流水线步骤定义。"""
    
    name: str
    description: str = ""
    status: StepStatus = StepStatus.PENDING
    
    # 执行结果
    output: Any = None
    error: str | None = None
    duration_ms: float = 0.0
    
    # 条件执行
    condition: str | None = None  # 可选的条件表达式


class PipelineState(BaseModel):
    """流水线执行状态。"""
    
    name: str = "pipeline"
    steps: list[PipelineStep] = Field(default_factory=list)
    current_step: int = 0
    is_complete: bool = False
    
    # 共享上下文 (步骤间传递数据)
    context: dict[str, Any] = Field(default_factory=dict)
    
    # 错误处理
    errors: list[str] = Field(default_factory=list)
    
    def get_step(self, name: str) -> PipelineStep | None:
        """按名称获取步骤。"""
        for step in self.steps:
            if step.name == name:
                return step
        return None
    
    def set_context(self, key: str, value: Any) -> None:
        """设置上下文值。"""
        self.context[key] = value
    
    def get_context(self, key: str, default: Any = None) -> Any:
        """获取上下文值。"""
        return self.context.get(key, default)


# ============================================================
# Pipeline Executor
# ============================================================

StepHandler = Callable[[PipelineState], Any]


class Pipeline:
    """流水线 - 顺序执行多个步骤。
    
    支持:
    - 顺序执行
    - 条件跳过
    - 错误处理
    - 上下文传递
    
    Usage:
        pipeline = Pipeline("process_document")
        pipeline.add_step("parse", lambda state: parser.run(state.get_context("file")))
        pipeline.add_step("analyze", lambda state: analyzer.run(state.get_context("document")))
        result = pipeline.run({"file": "/path/to/file.md"})
    """
    
    def __init__(self, name: str = "pipeline"):
        """初始化流水线。
        
        Args:
            name: 流水线名称
        """
        self.name = name
        self._steps: list[tuple[str, StepHandler, str | None]] = []
    
    def add_step(
        self,
        name: str,
        handler: StepHandler,
        condition: str | None = None,
        description: str = "",
    ) -> "Pipeline":
        """添加执行步骤。
        
        Args:
            name: 步骤名称
            handler: 步骤处理函数，接收 PipelineState，返回任意结果
            condition: 可选的条件表达式，为 False 时跳过
            description: 步骤描述
            
        Returns:
            self，支持链式调用
        """
        self._steps.append((name, handler, condition))
        return self
    
    def run(self, initial_context: dict[str, Any] | None = None) -> PipelineState:
        """执行流水线。
        
        Args:
            initial_context: 初始上下文
            
        Returns:
            执行后的 PipelineState
        """
        import time
        
        # 创建状态
        state = PipelineState(name=self.name)
        state.context = initial_context or {}
        
        # 创建步骤
        for name, handler, condition in self._steps:
            state.steps.append(PipelineStep(
                name=name,
                condition=condition,
            ))
        
        # 执行步骤
        for i, (name, handler, condition) in enumerate(self._steps):
            state.current_step = i
            step = state.steps[i]
            step.status = StepStatus.RUNNING
            
            # 检查条件
            if condition:
                try:
                    should_run = eval(condition, {"state": state, "context": state.context})
                    if not should_run:
                        step.status = StepStatus.SKIPPED
                        continue
                except Exception as e:
                    step.status = StepStatus.FAILED
                    step.error = f"Condition evaluation failed: {e}"
                    state.errors.append(step.error)
                    continue
            
            # 执行步骤
            start_time = time.time()
            try:
                result = handler(state)
                step.output = result
                step.status = StepStatus.COMPLETED
                
                # 自动将结果存入上下文
                state.set_context(f"{name}_result", result)
                
            except Exception as e:
                step.status = StepStatus.FAILED
                step.error = str(e)
                state.errors.append(f"Step '{name}' failed: {e}")
            
            step.duration_ms = (time.time() - start_time) * 1000
        
        state.is_complete = True
        return state


# ============================================================
# Document Processing Pipeline
# ============================================================

class DocumentPipeline:
    """文档处理流水线 - 组合多个 Agent 完成文档处理。
    
    标准流程:
    1. 解析文件 (ParserAgent)
    2. 识别结构 (StructureAgent)
    3. 存储文档 (FileStore)
    4. 建立索引 (VectorIndex)
    
    Usage:
        from ai_midlayer.agents import ParserAgent, StructureAgent
        from ai_midlayer.knowledge import FileStore, VectorIndex
        
        pipeline = DocumentPipeline(
            parser=ParserAgent(),
            structure_agent=StructureAgent(),
            store=FileStore(".midlayer"),
            index=VectorIndex(".midlayer"),
        )
        result = pipeline.process("/path/to/file.md")
    """
    
    def __init__(
        self,
        parser=None,
        structure_agent=None,
        store=None,
        index=None,
    ):
        """初始化文档处理流水线。
        
        Args:
            parser: ParserAgent 实例
            structure_agent: StructureAgent 实例
            store: FileStore 实例
            index: VectorIndex 实例
        """
        self.parser = parser
        self.structure_agent = structure_agent
        self.store = store
        self.index = index
    
    def process(self, file_path: str) -> dict[str, Any]:
        """处理单个文件。
        
        Args:
            file_path: 文件路径
            
        Returns:
            处理结果字典
        """
        result = {
            "file_path": file_path,
            "success": False,
            "document": None,
            "structure": None,
            "doc_id": None,
            "chunks_indexed": 0,
            "errors": [],
        }
        
        # 1. 解析文件
        if self.parser:
            try:
                document = self.parser.parse(file_path)
                if document:
                    result["document"] = document
                else:
                    result["errors"].append("Parsing failed")
                    return result
            except Exception as e:
                result["errors"].append(f"Parse error: {e}")
                return result
        
        # 2. 识别结构
        if self.structure_agent and result["document"]:
            try:
                structure = self.structure_agent.analyze(result["document"])
                result["structure"] = structure
            except Exception as e:
                result["errors"].append(f"Structure analysis error: {e}")
        
        # 3. 存储文档
        if self.store:
            try:
                doc_id = self.store.add_file(file_path)
                result["doc_id"] = doc_id
            except Exception as e:
                result["errors"].append(f"Storage error: {e}")
        
        # 4. 建立索引
        if self.index and result["document"]:
            try:
                chunks = self.index.index_document(result["document"])
                result["chunks_indexed"] = chunks
            except Exception as e:
                result["errors"].append(f"Indexing error: {e}")
        
        result["success"] = len(result["errors"]) == 0
        return result
    
    def process_directory(self, dir_path: str, recursive: bool = True) -> list[dict[str, Any]]:
        """处理目录下的所有文件。
        
        Args:
            dir_path: 目录路径
            recursive: 是否递归处理子目录
            
        Returns:
            处理结果列表
        """
        from pathlib import Path
        
        results = []
        path = Path(dir_path)
        
        if not path.is_dir():
            return [{"error": f"Not a directory: {dir_path}"}]
        
        files = path.rglob("*") if recursive else path.glob("*")
        
        for file_path in files:
            if file_path.is_file() and not file_path.name.startswith("."):
                result = self.process(str(file_path))
                results.append(result)
        
        return results
