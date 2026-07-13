"""Base interfaces for NervAI channels."""
from typing import Protocol, Any
from uuid import uuid4
import voluptuous as vol
from homeassistant.exceptions import HomeAssistantError, ServiceNotFound
from homeassistant.core import Context

CONFIRMATION_REQUIRED_DOMAINS = {"lock", "alarm_control_panel", "cover"} # Cover: Garaj kapıları vs.

class HomeAssistantBridge(Protocol):
    """Interface for channels to interact with Home Assistant securely."""
    
    # Bellekte bekleyen kritik komutlar için sözlük. (Token: ToolCall)
    _pending_actions: dict[str, Any]

    async def execute_tool_call(self, call: dict, chat_id: str) -> dict:
        """Evaluate and safely execute a tool call from the LLM."""
        args = call.get("arguments", {})
        domain = args.get("domain")
        service = args.get("service")
        entity_id = args.get("entity_id")

        if domain in CONFIRMATION_REQUIRED_DOMAINS:
            token = str(uuid4())[:8] # Kısa token
            self._pending_actions[token] = call
            return {
                "status": "confirmation_required", 
                "token": token,
                "message": f"Security Alert: Execution of {domain}.{service} requires manual confirmation. Reply with '/confirm {token}' to proceed."
            }
        
        return await self._call_service_safe(domain, service, entity_id, args.get("data"))

    async def _call_service_safe(self, domain: str, service: str, entity_id: str, data: dict | None = None) -> dict:
        """Execute a service and swallow/format errors."""
        ... # (Implementation __init__.py içinde yapılacak)

    async def get_state(self, entity_id: str) -> str | None:
        """Get the state of an entity."""
        ...