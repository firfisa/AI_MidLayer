"""LLM 增强的 Agent - 使用真正的 AI 推理。

提供 LLM 能力:
- 智能分析 (Orient)
- 决策推理 (Decide)
- 自我反思 (Reflect)
"""

from typing import Any

from ai_midlayer.agents.protocols import AgentState
from ai_midlayer.llm import LiteLLMClient, LLMConfig, Message


class LLMAgentMixin:
    """LLM 增强的混入类。
    
    可以被任何 Agent 子类使用来添加 LLM 能力。
    不需要继承 BaseAgent，可以独立使用进行 LLM 调用。
    
    提供 LLM 调用方法:
    - orient_with_llm(): LLM 分析观察结果
    - decide_with_llm(): LLM 决定行动
    - reflect_with_llm(): LLM 反思结果
    
    Usage as mixin:
        class MyAgent(LLMAgentMixin, BaseAgent):
            def __init__(self, llm_config=None):
                LLMAgentMixin.__init__(self, llm_config=llm_config)
                BaseAgent.__init__(self, max_iterations=3)
    
    Usage standalone:
        mixin = LLMAgentMixin(llm_config=config)
        result = mixin._call_llm("Hello!")
    """
    
    llm_client: LiteLLMClient | None = None
    system_prompt: str = ""
    
    def __init__(
        self,
        llm_client: LiteLLMClient | None = None,
        llm_config: LLMConfig | None = None,
        system_prompt: str | None = None,
    ):
        """初始化 LLM 能力。
        
        Args:
            llm_client: 可选的已配置 LLM 客户端
            llm_config: LLM 配置（如果不提供 client）
            system_prompt: 系统提示
        """
        self.system_prompt = system_prompt or self._default_system_prompt()
        
        if llm_client:
            self.llm_client = llm_client
        elif llm_config:
            self.llm_client = LiteLLMClient(llm_config)
        else:
            self.llm_client = None
    
    def _default_system_prompt(self) -> str:
        """默认系统提示。"""
        return """You are an intelligent agent following the OODA (Observe-Orient-Decide-Act) loop with Reflexion.

Your task is to process information systematically:
1. OBSERVE: Gather relevant information
2. ORIENT: Analyze the situation and identify gaps
3. DECIDE: Choose the best action
4. ACT: Execute the action
5. REFLECT: Evaluate results and learn

Be concise, precise, and focused on the task at hand."""
    
    def _call_llm(self, prompt: str, context: dict | None = None) -> str:
        """调用 LLM 获取响应。
        
        Args:
            prompt: 用户提示
            context: 可选的上下文信息
            
        Returns:
            LLM 响应，如果没有配置 LLM 则返回空字符串
        """
        if not self.llm_client:
            return ""
        
        # 构建完整提示
        full_prompt = prompt
        if context:
            context_str = "\n".join(f"- {k}: {v}" for k, v in context.items())
            full_prompt = f"Context:\n{context_str}\n\nTask:\n{prompt}"
        
        return self.llm_client.chat(full_prompt, system=self.system_prompt)
    
    def orient_with_llm(self, state: AgentState, observation: Any) -> str:
        """使用 LLM 进行分析。"""
        prompt = f"""Based on the following observation, analyze the current situation:

Observation:
{observation}

Previous actions: {len(state.actions)}
Previous reflections: {state.reflections[-3:] if state.reflections else 'None'}

Provide a brief analysis including:
1. What is the current state?
2. What are the key insights?
3. What gaps or issues need attention?"""
        
        return self._call_llm(prompt)
    
    def decide_with_llm(self, state: AgentState, orientation: Any) -> str:
        """使用 LLM 进行决策。"""
        prompt = f"""Based on the analysis, decide the next action:

Analysis:
{orientation}

Iteration: {state.iteration + 1}/{state.max_iterations}
Previous decisions: {state.decisions[-3:] if state.decisions else 'None'}

Choose one specific action and explain why. Format:
ACTION: [action name]
REASON: [brief explanation]"""
        
        return self._call_llm(prompt)
    
    def reflect_with_llm(self, state: AgentState, action_result: Any) -> str:
        """使用 LLM 进行反思。"""
        prompt = f"""Reflect on the action result:

Action Result:
{action_result}

Original Goal: {state.input}
Iteration: {state.iteration + 1}/{state.max_iterations}

Answer these questions:
1. Was the action successful?
2. What did we learn?
3. Do we need to refine our approach? (Yes/No and why)"""
        
        return self._call_llm(prompt)
    
    def has_llm(self) -> bool:
        """检查是否配置了 LLM。"""
        return self.llm_client is not None
