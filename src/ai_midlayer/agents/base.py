"""Agent 基类实现 - OODA + Reflexion 循环。

基于 protocols.py 中定义的接口，实现可扩展的 Agent 基类：
- OODA 循环: Observe → Orient → Decide → Act
- Reflexion: Reflect → Refine 自我修正
- 依赖注入: LLM Provider、Tools、Callbacks 可配置
- 高内聚低耦合: 每个方法职责单一

Architecture alignment: L3 Agent Layer → OODA + ReAct + Reflexion
"""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from ai_midlayer.agents.protocols import (
    AgentCallback,
    AgentPhase,
    AgentState,
    LLMProvider,
    Tool,
)


StateT = TypeVar("StateT", bound=AgentState)


class BaseAgent(ABC, Generic[StateT]):
    """Agent 基类 - 实现 OODA + Reflexion 循环。
    
    子类需要实现:
    - observe(): 观察当前状态
    - orient(): 分析差距
    - decide(): 决策动作
    - act(): 执行动作
    - reflect(): 反思结果 (可选覆盖)
    - should_refine(): 是否需要修正 (可选覆盖)
    - create_state(): 创建状态对象
    
    遵循开闭原则: 对扩展开放，对修改封闭。
    """
    
    def __init__(
        self,
        max_iterations: int = 3,
        llm: LLMProvider | None = None,
        tools: list[Tool] | None = None,
        callbacks: list[AgentCallback] | None = None,
    ):
        """初始化 Agent。
        
        Args:
            max_iterations: 最大迭代次数，防止死循环
            llm: LLM Provider，可注入不同实现
            tools: 可用工具列表
            callbacks: 回调列表，用于监控
        """
        self.max_iterations = max_iterations
        self.llm = llm
        self.tools = tools or []
        self.callbacks = callbacks or []
    
    # ============================================================
    # Lifecycle Methods (子类实现)
    # ============================================================
    
    @abstractmethod
    def create_state(self, input_data: Any) -> StateT:
        """创建初始状态对象。
        
        子类实现，返回特定类型的状态对象。
        """
        pass
    
    @abstractmethod
    def observe(self, state: StateT) -> Any:
        """OODA - Observe: 观察当前状态。
        
        Args:
            state: 当前状态
            
        Returns:
            观察结果
        """
        pass
    
    @abstractmethod
    def orient(self, state: StateT, observation: Any) -> Any:
        """OODA - Orient: 分析当前与目标的差距。
        
        Args:
            state: 当前状态
            observation: 观察结果
            
        Returns:
            分析结果
        """
        pass
    
    @abstractmethod
    def decide(self, state: StateT, orientation: Any) -> Any:
        """OODA - Decide: 决策下一步动作。
        
        Args:
            state: 当前状态
            orientation: 分析结果
            
        Returns:
            决策结果
        """
        pass
    
    @abstractmethod
    def act(self, state: StateT, decision: Any) -> Any:
        """OODA - Act: 执行决策的动作。
        
        Args:
            state: 当前状态
            decision: 决策结果
            
        Returns:
            动作结果
        """
        pass
    
    def reflect(self, state: StateT, action_result: Any) -> str:
        """Reflexion - Reflect: 反思动作结果。
        
        默认实现返回空反思，子类可覆盖实现深度反思。
        
        Args:
            state: 当前状态
            action_result: 动作结果
            
        Returns:
            反思内容
        """
        return "Action completed, no refinement needed."
    
    def should_refine(self, state: StateT, reflection: str) -> bool:
        """Reflexion - 判断是否需要修正。
        
        默认实现：如果反思包含 "need" 或 "should" 则需要修正。
        子类可覆盖实现更精确的判断。
        
        Args:
            state: 当前状态
            reflection: 反思内容
            
        Returns:
            是否需要修正
        """
        keywords = ["need", "should", "must", "error", "wrong", "fix"]
        return any(kw in reflection.lower() for kw in keywords)
    
    def finalize(self, state: StateT) -> Any:
        """完成处理，返回最终输出。
        
        默认实现返回 state.output，子类可覆盖。
        """
        return state.output
    
    # ============================================================
    # Callback Helpers
    # ============================================================
    
    def _notify_phase_start(self, phase: AgentPhase, state: StateT) -> None:
        """通知所有回调：阶段开始。"""
        for callback in self.callbacks:
            try:
                callback.on_phase_start(phase, state)
            except Exception:
                pass  # 回调失败不影响主流程
    
    def _notify_phase_end(self, phase: AgentPhase, state: StateT) -> None:
        """通知所有回调：阶段结束。"""
        for callback in self.callbacks:
            try:
                callback.on_phase_end(phase, state)
            except Exception:
                pass
    
    def _notify_iteration_complete(self, iteration: int, state: StateT) -> None:
        """通知所有回调：迭代完成。"""
        for callback in self.callbacks:
            try:
                callback.on_iteration_complete(iteration, state)
            except Exception:
                pass
    
    def _notify_error(self, error: Exception, state: StateT) -> None:
        """通知所有回调：发生错误。"""
        for callback in self.callbacks:
            try:
                callback.on_error(error, state)
            except Exception:
                pass
    
    # ============================================================
    # Main Execution Loop (OODA + Reflexion)
    # ============================================================
    
    def run(self, input_data: Any) -> Any:
        """执行 OODA + Reflexion 循环。
        
        流程:
        1. OBSERVE → ORIENT → DECIDE → ACT
        2. REFLECT → 判断是否需要 REFINE
        3. 如果需要修正，回到 OBSERVE 继续迭代
        4. 直到满意或达到最大迭代次数
        
        Args:
            input_data: 输入数据
            
        Returns:
            处理结果
        """
        # 创建初始状态
        state = self.create_state(input_data)
        state.max_iterations = self.max_iterations
        
        # OODA + Reflexion 循环
        while not state.is_complete and state.iteration < state.max_iterations:
            try:
                # === OBSERVE ===
                state.phase = AgentPhase.OBSERVE
                self._notify_phase_start(AgentPhase.OBSERVE, state)
                observation = self.observe(state)
                state.add_observation(observation)
                self._notify_phase_end(AgentPhase.OBSERVE, state)
                
                # === ORIENT ===
                state.phase = AgentPhase.ORIENT
                self._notify_phase_start(AgentPhase.ORIENT, state)
                orientation = self.orient(state, observation)
                self._notify_phase_end(AgentPhase.ORIENT, state)
                
                # === DECIDE ===
                state.phase = AgentPhase.DECIDE
                self._notify_phase_start(AgentPhase.DECIDE, state)
                decision = self.decide(state, orientation)
                state.add_decision(decision)
                self._notify_phase_end(AgentPhase.DECIDE, state)
                
                # === ACT ===
                state.phase = AgentPhase.ACT
                self._notify_phase_start(AgentPhase.ACT, state)
                action_result = self.act(state, decision)
                state.add_action(action_result)
                self._notify_phase_end(AgentPhase.ACT, state)
                
                # === REFLECT (Reflexion) ===
                state.phase = AgentPhase.REFLECT
                self._notify_phase_start(AgentPhase.REFLECT, state)
                reflection = self.reflect(state, action_result)
                state.add_reflection(reflection)
                self._notify_phase_end(AgentPhase.REFLECT, state)
                
                # === REFINE 判断 ===
                if self.should_refine(state, reflection):
                    state.phase = AgentPhase.REFINE
                    self._notify_phase_start(AgentPhase.REFINE, state)
                    # 继续下一次迭代进行修正
                    self._notify_phase_end(AgentPhase.REFINE, state)
                else:
                    # 满意，完成
                    state.is_complete = True
                
                state.iteration += 1
                self._notify_iteration_complete(state.iteration, state)
                
            except Exception as e:
                state.add_error(str(e))
                self._notify_error(e, state)
                # 可以选择继续或终止，这里选择终止
                state.is_complete = True
        
        # 最终处理
        state.phase = AgentPhase.COMPLETE
        return self.finalize(state)
    
    async def arun(self, input_data: Any) -> Any:
        """异步执行 - 当前使用同步实现。
        
        TODO: 实现真正的异步版本
        """
        return self.run(input_data)
