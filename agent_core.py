"""
Agent Core Library for Sportsbook AI System

This module provides the foundation for building AI agents using Together AI.
Includes:
- TogetherAIClient: Wrapper for Together AI API
- Tool: Base class for agent tools
- Agent: ReAct-style agent with tool execution loop
"""

import os
import json
import logging
from typing import Any, Callable, Optional
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("agent_core")

# =============================================================================
# Together AI Client
# =============================================================================

@dataclass
class TogetherAIClient:
    """
    Simple client for Together AI API.
    
    Supports:
    - Chat completions with tool/function calling
    - Streaming (optional)
    
    Model Recommendations:
    - For complex reasoning: "moonshotai/Kimi-K2-Instruct" (Kimi 2.5)
    - For fast responses: "meta-llama/Llama-3.3-70B-Instruct-Turbo"
    - For function calling: "mistralai/Mixtral-8x22B-Instruct-v0.1"
    """
    
    api_key: str = field(default_factory=lambda: os.environ.get("TOGETHER_API_KEY", ""))
    base_url: str = "https://api.together.xyz/v1"
    default_model: str = "meta-llama/Llama-3.3-70B-Instruct-Turbo"
    
    def __post_init__(self):
        if not self.api_key:
            raise ValueError("TOGETHER_API_KEY environment variable not set")
        
        # Import requests here to keep dependencies minimal at import time
        import requests
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        })
    
    def chat(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        tools: Optional[list[dict]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> dict:
        """
        Send a chat completion request.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model to use (defaults to self.default_model)
            tools: Optional list of tool definitions for function calling
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            
        Returns:
            Response dict from Together AI
        """
        payload = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        
        try:
            response = self._session.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Together AI request failed: {e}")
            raise


# =============================================================================
# Tool System
# =============================================================================

@dataclass
class Tool:
    """
    Represents a tool that an agent can use.
    
    Example:
        def check_health() -> str:
            return "OK"
        
        health_tool = Tool(
            name="check_health",
            description="Check the API health status",
            parameters={},
            function=check_health
        )
    """
    name: str
    description: str
    parameters: dict  # JSON Schema for parameters
    function: Callable[..., Any]
    
    def to_openai_schema(self) -> dict:
        """Convert to OpenAI-compatible tool schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": list(self.parameters.keys())
                }
            }
        }
    
    def execute(self, **kwargs) -> Any:
        """Execute the tool with given arguments."""
        try:
            result = self.function(**kwargs)
            logger.info(f"Tool '{self.name}' executed successfully")
            return result
        except Exception as e:
            logger.error(f"Tool '{self.name}' failed: {e}")
            return f"Error: {str(e)}"


# =============================================================================
# Agent Base Class
# =============================================================================

class Agent(ABC):
    """
    Base class for ReAct-style agents.
    
    Subclasses should:
    1. Define tools in __init__
    2. Implement get_system_prompt()
    
    The agent loop:
    1. Send messages to LLM
    2. If LLM calls a tool, execute it and append result
    3. Repeat until LLM returns final answer (no tool calls)
    """
    
    def __init__(
        self,
        client: TogetherAIClient,
        model: Optional[str] = None,
        max_iterations: int = 10
    ):
        self.client = client
        self.model = model or client.default_model
        self.max_iterations = max_iterations
        self.tools: list[Tool] = []
        self.logger = logging.getLogger(self.__class__.__name__)
    
    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the system prompt for this agent."""
        pass
    
    def add_tool(self, tool: Tool):
        """Register a tool with this agent."""
        self.tools.append(tool)
        self.logger.info(f"Registered tool: {tool.name}")
    
    def _get_tool_schemas(self) -> list[dict]:
        """Get OpenAI-format tool schemas for all registered tools."""
        return [t.to_openai_schema() for t in self.tools]
    
    def _find_tool(self, name: str) -> Optional[Tool]:
        """Find a tool by name."""
        for t in self.tools:
            if t.name == name:
                return t
        return None
    
    def run(self, user_message: str) -> str:
        """
        Run the agent with a user message.
        
        Returns the final response after tool execution loop.
        """
        messages = [
            {"role": "system", "content": self.get_system_prompt()},
            {"role": "user", "content": user_message}
        ]
        
        tool_schemas = self._get_tool_schemas() if self.tools else None
        
        for iteration in range(self.max_iterations):
            self.logger.info(f"Iteration {iteration + 1}/{self.max_iterations}")
            
            response = self.client.chat(
                messages=messages,
                model=self.model,
                tools=tool_schemas
            )
            
            choice = response.get("choices", [{}])[0]
            message = choice.get("message", {})
            
            # Check for tool calls
            tool_calls = message.get("tool_calls", [])
            
            if not tool_calls:
                # No tool calls = final answer
                final_content = message.get("content", "")
                self.logger.info("Agent completed (no more tool calls)")
                return final_content
            
            # Append assistant message with tool calls
            messages.append(message)
            
            # Execute each tool call
            for tc in tool_calls:
                func = tc.get("function", {})
                tool_name = func.get("name", "")
                tool_args_str = func.get("arguments", "{}")
                
                try:
                    tool_args = json.loads(tool_args_str)
                except json.JSONDecodeError:
                    tool_args = {}
                
                self.logger.info(f"Calling tool: {tool_name} with args: {tool_args}")
                
                tool = self._find_tool(tool_name)
                if tool:
                    result = tool.execute(**tool_args)
                else:
                    result = f"Error: Unknown tool '{tool_name}'"
                
                # Append tool result
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", ""),
                    "name": tool_name,
                    "content": str(result)
                })
        
        self.logger.warning("Max iterations reached")
        return "Error: Agent reached maximum iterations without completing."


# =============================================================================
# Utility Functions
# =============================================================================

def create_tool(
    name: str,
    description: str,
    parameters: dict,
    function: Callable
) -> Tool:
    """
    Factory function to create a Tool.
    
    Args:
        name: Tool name (used in function calling)
        description: What the tool does (shown to LLM)
        parameters: JSON Schema dict describing parameters
        function: The actual Python function to call
        
    Returns:
        Tool instance
    """
    return Tool(
        name=name,
        description=description,
        parameters=parameters,
        function=function
    )


# =============================================================================
# Quick Test
# =============================================================================

if __name__ == "__main__":
    # Quick sanity check
    print("Agent Core Library loaded successfully.")
    
    # Test client initialization (will fail without API key)
    try:
        client = TogetherAIClient()
        print(f"Client initialized with model: {client.default_model}")
    except ValueError as e:
        print(f"Client init skipped: {e}")
