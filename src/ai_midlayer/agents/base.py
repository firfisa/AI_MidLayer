"""Base Agent class with OODA + Reflexion loop structure."""

from abc import ABC, abstractmethod
from typing import Any, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class AgentState(BaseModel):
    """Base state for agents."""
    
    input: Any
    observations: list[Any] = []
    decisions: list[Any] = []
    actions: list[Any] = []
    reflections: list[str] = []
    output: Any = None
    iteration: int = 0
    max_iterations: int = 3
    is_complete: bool = False


class Agent(ABC):
    """Base Agent class implementing OODA + Reflexion loop.
    
    OODA: Observe → Orient → Decide → Act
    Reflexion: Reflect on results, refine if needed
    """
    
    def __init__(self, max_iterations: int = 3):
        """Initialize the agent.
        
        Args:
            max_iterations: Maximum number of OODA loops before stopping.
        """
        self.max_iterations = max_iterations
    
    @abstractmethod
    def observe(self, state: AgentState) -> Any:
        """Observe the current state.
        
        Args:
            state: Current agent state.
            
        Returns:
            Observations about the current state.
        """
        pass
    
    @abstractmethod
    def orient(self, state: AgentState, observation: Any) -> Any:
        """Orient - analyze the gap between current and desired state.
        
        Args:
            state: Current agent state.
            observation: Current observations.
            
        Returns:
            Analysis of what needs to be done.
        """
        pass
    
    @abstractmethod
    def decide(self, state: AgentState, orientation: Any) -> Any:
        """Decide on the next action.
        
        Args:
            state: Current agent state.
            orientation: The orientation analysis.
            
        Returns:
            Decision about what to do next.
        """
        pass
    
    @abstractmethod
    def act(self, state: AgentState, decision: Any) -> Any:
        """Execute the decided action.
        
        Args:
            state: Current agent state.
            decision: The decision to act on.
            
        Returns:
            Result of the action.
        """
        pass
    
    def reflect(self, state: AgentState, result: Any) -> str:
        """Reflect on the result and determine if refinement is needed.
        
        Args:
            state: Current agent state.
            result: Result of the last action.
            
        Returns:
            Reflection on the result.
        """
        # Default: no reflection needed
        return "Result acceptable, no refinement needed."
    
    def should_continue(self, state: AgentState) -> bool:
        """Determine if the agent should continue iterating.
        
        Args:
            state: Current agent state.
            
        Returns:
            True if should continue, False otherwise.
        """
        return not state.is_complete and state.iteration < state.max_iterations
    
    def run(self, input_data: Any) -> Any:
        """Run the agent with the OODA + Reflexion loop.
        
        Args:
            input_data: Input data for the agent.
            
        Returns:
            The final output from the agent.
        """
        state = AgentState(
            input=input_data,
            max_iterations=self.max_iterations
        )
        
        while self.should_continue(state):
            # OODA Loop
            observation = self.observe(state)
            state.observations.append(observation)
            
            orientation = self.orient(state, observation)
            
            decision = self.decide(state, orientation)
            state.decisions.append(decision)
            
            result = self.act(state, decision)
            state.actions.append(result)
            
            # Reflexion
            reflection = self.reflect(state, result)
            state.reflections.append(reflection)
            
            state.iteration += 1
        
        return state.output
