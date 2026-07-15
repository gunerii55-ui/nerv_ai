import logging

_LOGGER = logging.getLogger(__name__)

class OpenAIProvider:
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self._api_key = api_key
        self._model = model
        self._client = None

    def _get_client(self):
        # Tembel Yükleme (Lazy Loading): HA Event Loop bloklanmasını engeller.
        # Sadece mesaj gönderileceği an import edilir.
        if not self._client:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=self._api_key)
        return self._client

    async def send_message(self, messages: list, tools: list = None):
        client = self._get_client()
        
        kwargs = {
            "model": self._model,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools

        try:
            response = await client.chat.completions.create(**kwargs)
            return response.choices[0].message
        except Exception as e:
            _LOGGER.error(f"NervAI OpenAI Hatası: {e}")
            raise