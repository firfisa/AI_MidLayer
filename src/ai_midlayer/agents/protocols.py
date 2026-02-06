"""Agent 协议和抽象接口定义。

遵循高内聚低耦合原则：
- 定义抽象协议，具体实现可替换
- 依赖注入，组件通过接口通信
- 插件化架构，易于扩展

Architecture alignment: L3 Agent Layer
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Generic, Protocol, TypeVar

from pydantic import BaseModel, Field


# ============================================================
# Type Variables for Generic Agent Support
# ============================================================

InputT = TypeVar("InputT")  # Agent 输入类型
OutputT = TypeVar("OutputT")  # Agent 输出类型
StateT = TypeVar("StateT", bound="AgentState")  # Agent 状态类型


# ============================================================
# Agent State Models
# ============================================================

class AgentPhase(str, Enum):
    """Agent 当前执行阶段 (OODA 循环)。"""
    
    OBSERVE = "observe"      # 观察当前状态
    ORIENT = "orient"        # 分析差距
    DECIDE = "decide"        # 决策动作
    ACT = "act"              # 执行动作
    REFLECT = "reflect"      # 反思结果 (Reflexion)
    REFINE = "refine"        # 修正改进
    COMPLETE = "complete"    # 完成


class AgentState(BaseModel):
    """Agent 执行状态基类。
    
    可被子类继承扩展，添加特定领域的状态字段。
    """
    
    # 基础状态
    input: Any = None
    output: Any = None
    
    # 执行追踪
    phase: AgentPhase = AgentPhase.OBSERVE
    iteration: int = 0
    max_iterations: int = 3
    is_complete: bool = False
    
    # 历史记录 (用于 Reflexion)
    observations: list[Any] = Field(default_factory=list)
    decisions: list[Any] = Field(default_factory=list)
    actions: list[Any] = Field(default_factory=list)
    reflections: list[str] = Field(default_factory=list)
    
    # 错误处理
    errors: list[str] = Field(default_factory=list)
    
    def add_observation(self, obs: Any) -> None:
        """添加观察记录。"""
        self.observations.append(obs)
    
    def add_decision(self, decision: Any) -> None:
        """添加决策记录。"""
        self.decisions.append(decision)
    
    def add_action(self, action: Any) -> None:
        """添加动作记录。"""
        self.actions.append(action)
    
    def add_reflection(self, reflection: str) -> None:
        """添加反思记录。"""
        self.reflections.append(reflection)
    
    def add_error(self, error: str) -> None:
        """添加错误记录。"""
        self.errors.append(error)


# ============================================================
# LLM Provider Protocol (依赖注入接口)
# ============================================================

class LLMProvider(Protocol):
    """LLM 调用协议 - 可注入不同的 LLM 实现。
    
    遵循依赖倒置原则：Agent 依赖抽象接口，不依赖具体实现。
    """
    
    def complete(self, prompt: str, **kwargs) -> str:
        """同步调用 LLM 生成响应。"""
        ...
    
    async def acomplete(self, prompt: str, **kwargs) -> str:
        """异步调用 LLM 生成响应。"""
        ...


# ============================================================
# Tool Protocol (可插拔工具接口)
# ============================================================

class Tool(Protocol):
    """工具协议 - Agent 可使用的工具。"""
    
    @property
    def name(self) -> str:
        """工具名称。"""
        ...
    
    @property
    def description(self) -> str:
        """工具描述。"""
        ...
    
    def execute(self, **kwargs) -> Any:
        """执行工具。"""
        ...


# ============================================================
# Agent Protocol (核心接口)
# ============================================================

class AgentProtocol(Protocol[InputT, OutputT]):
    """Agent 协议 - 所有 Agent 必须实现的接口。
    
    使用 Protocol 而非 ABC，支持结构化子类型。
    """
    
    def run(self, input_data: InputT) -> OutputT:
        """执行 Agent 处理流程。"""
        ...
    
    async def arun(self, input_data: InputT) -> OutputT:
        """异步执行 Agent 处理流程。"""
        ...


# ============================================================
# Callback Protocol (可扩展钩子)
# ============================================================

class AgentCallback(Protocol):
    """Agent 回调协议 - 用于监控和日志。"""
    
    def on_phase_start(self, phase: AgentPhase, state: AgentState) -> None:
        """阶段开始回调。"""
        ...
    
    def on_phase_end(self, phase: AgentPhase, state: AgentState) -> None:
        """阶段结束回调。"""
        ...
    
    def on_iteration_complete(self, iteration: int, state: AgentState) -> None:
        """迭代完成回调。"""
        ...
    
    def on_error(self, error: Exception, state: AgentState) -> None:
        """错误回调。"""
        ...
