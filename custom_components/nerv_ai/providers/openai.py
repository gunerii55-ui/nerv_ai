"""OpenAI Provider for NervAI."""
import logging
from openai import AsyncOpenAI
from .base import LLMProvider

_LOGGER = logging.getLogger(__name__)

try:
    import tiktoken
    _ENC = tiktoken.get_encoding("cl100k_base")
    HAS_TIKTOKEN = True
except ImportError:
    HAS_TIKTOKEN = False
    _LOGGER.warning("NervAI: tiktoken not found. Using text length fallback for token counting. This is safe for 32-bit ARM HA OS.")

class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model
        self._max_context_tokens = 120000 # gpt-4o-mini için güvenli sınır

    async def send_message(self, context: list[dict], user_message: str) -> str:
        """Mesajı OpenAI'ye gönder ve cevabı dön."""
        messages = context.copy()
        messages.append({"role": "user", "content": user_message})
        
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages
        )
        return response.choices[0].message.content

    async def list_models(self) -> list[str]:
        return ["gpt-4o-mini", "gpt-4o"]

    def count_tokens(self, text: str) -> int:
        if HAS_TIKTOKEN:
            return len(_ENC.encode(text))
        # Fallback: Kaba yaklaşım (Türkçe dahil çok dilli ortamlar için // 3 daha güvenlidir)
        return len(text) // 3

    @property
    def max_context_tokens(self) -> int:
        return self._max_context_tokens