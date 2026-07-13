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
        # 1. Hafızayı Getir (Sabit kurallar + Son N konuşma)
        raw_context = await self._store.build_context(chat_id)
        
        # 2. Token Limit Kontrolü ve Kırpma (Sadece conversation_log kırpılır)
        # TODO: Burada raw_context listesini sondan başa doğru tarayıp
        # self._provider.max_context_tokens sınırına kadar olanları tutacağız.
        # Sabit kurallar (learned_facts) asla kırpılmayacak.
        
        context_to_send = raw_context # Şimdilik taslak
        
        # 3. LLM'e Sor
        try:
            reply = await self._provider.send_message(context_to_send, user_message)
        except Exception as e:
            _LOGGER.error(f"NervAI: LLM Provider error: {e}")
            return "Sistem hatası: Yapay zeka sağlayıcısına ulaşılamadı."

        # 4. Yeni mesajlaşmayı veri tabanına kaydet
        await self._store.save_turn(chat_id, user_message, reply)
        
        return reply