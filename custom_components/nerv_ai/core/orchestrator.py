import logging
import json
import asyncio

_LOGGER = logging.getLogger(__name__)

class ConversationOrchestrator:
    def __init__(self, store, provider, bridge):
        self._store = store
        self._provider = provider
        self._bridge = bridge

    async def _get_device_context(self):
        # HASS'taki tüm ışıkları çek ve LLM'e bir 'kroki' olarak gönder
        entities = await self._bridge.get_available_entities("light")
        device_map = "\n".join([f"- Name: {e['name']}, ID: {e['id']}" for e in entities])
        return f"Şu an evdeki ışıklar:\n{device_map}"

    async def handle_message(self, chat_id: str, user_message: str) -> str:
        # Sistem prompt'una dinamik cihaz listesini ekle
        device_context = await self._get_device_context()
        system_prompt = (
            "Sen NervAI, ev asistanısın. Aşağıdaki ışık listesini kullanarak komutları uygula. "
            f"{device_context}\n"
            "Kullanıcı 'mutfak' derse listedeki eşleşen ID'yi kullan."
        )
        
        context = [{"role": "system", "content": system_prompt}]
        raw = await self._store.build_context(chat_id)
        context.extend(raw["recent_log"])
        context.append({"role": "user", "content": user_message})

        response_msg = await self._provider.send_message(context, tools=self._tools)
        
        if response_msg.tool_calls:
            for tool_call in response_msg.tool_calls:
                args = json.loads(tool_call.function.arguments)
                # LLM artık ID'yi bildiği için execute_service hatasız çalışır
                result = await self._bridge.execute_service(**args)
                return f"İşlem sonucu: {result.get('status', 'ok')}"
        
        return response_msg.content or "Anlayamadım."