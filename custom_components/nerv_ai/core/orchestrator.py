"""Central orchestrator connecting Channels, Memory, and LLM."""
import logging
from typing import Any
from custom_components.nerv_ai.providers.base import LLMProvider

_LOGGER = logging.getLogger(__name__)

class ConversationOrchestrator:
    def __init__(self, store: Any, provider: LLMProvider): # store type hint şimdilik Any, store.py yazılınca eklenecek
        self._store = store
        self._provider = provider

    async def handle_message(self, chat_id: str, user_message: str) -> str:
        """Handle incoming message flow."""
        raw_context = await self._store.build_context(chat_id)
        
        context_to_send = []
        
        if raw_context["facts"]:
            facts_str = "\n".join([f"{f['key']}: {f['value']}" for f in raw_context["facts"]])
            context_to_send.append({"role": "system", "content": f"Bildiğin kesin kurallar:\n{facts_str}"})
            
        context_to_send.extend(raw_context["recent_log"])
        
        try:
            reply = await self._provider.send_message(context_to_send, user_message)
        except Exception as e:
            _LOGGER.error(f"NervAI: LLM Provider error: {e}")
            return "Sistem hatası: Yapay zeka sağlayıcısına ulaşılamadı."

        await self._store.save_turn(chat_id, user_message, reply)
        
        return reply