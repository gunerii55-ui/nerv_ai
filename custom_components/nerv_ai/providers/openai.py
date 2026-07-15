import logging
import asyncio

_LOGGER = logging.getLogger(__name__)

class OpenAIProvider:
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self._api_key = api_key
        self._model = model
        self._client = None

    async def _get_client(self):
        if not self._client:
            def _init_client_sync():
                # Import ve Client Instantiation ana loop'tan izole
                from openai import AsyncOpenAI
                return AsyncOpenAI(api_key=self._api_key)
            
            self._client = await asyncio.to_thread(_init_client_sync)
        return self._client

    async def send_message(self, messages: list, tools: list = None):
        client = await self._get_client()
        
        kwargs = {"model": self._model, "messages": messages}
        if tools: kwargs["tools"] = tools

        try:
            # API çağrısı zaten awaitable, bloklamaz
            response = await client.chat.completions.create(**kwargs)
            return response.choices[0].message
        except Exception as e:
            _LOGGER.error(f"OpenAI Error: {e}")
            raise