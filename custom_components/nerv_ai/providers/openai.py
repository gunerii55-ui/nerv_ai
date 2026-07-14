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
    _LOGGER.warning("NervAI: tiktoken not found. Using text length fallback.")

class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model
        self._max_context_tokens = 120000

    async def send_message(self, context: list[dict], tools: list[dict] | None = None) -> dict:
        """Mesajı gönder ve Raw Response Objeyi dön."""
        kwargs = {
            "model": self._model,
            "messages": context,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
            
        response = await self._client.chat.completions.create(**kwargs)
        return response.choices[0].message

    async def list_models(self) -> list[str]:
        return ["gpt-4o-mini", "gpt-4o"]

    def count_tokens(self, text: str) -> int:
        if HAS_TIKTOKEN:
            return len(_ENC.encode(text))
        return len(text) // 3

    @property
    def max_context_tokens(self) -> int:
        return self._max_context_tokens