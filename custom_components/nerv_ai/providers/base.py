"""Base Protocol for LLM Providers."""
from typing import Protocol, runtime_checkable, TypedDict, List, Tuple

class ToolCall(TypedDict):
    name: str
    arguments: dict
    tool_call_id: str

@runtime_checkable
class LLMProvider(Protocol):
    async def send_message(self, context: list[dict], user_message: str, tools: list[dict] = None) -> Tuple[str | None, List[ToolCall]]:
        """
        Send message to LLM and get the response.
        Returns a tuple: (text_reply, list_of_tool_calls)
        If the model only made a tool call, text_reply will be None.
        """
        ...

    async def list_models(self) -> list[str]:
        """List available models for UI config flow."""
        ...

    def count_tokens(self, text: str) -> int:
        """Count tokens synchronously."""
        ...

    @property
    def max_context_tokens(self) -> int:
        """Maximum allowed tokens for the context window."""
        ...