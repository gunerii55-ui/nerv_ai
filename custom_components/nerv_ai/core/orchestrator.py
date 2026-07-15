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
        # Tüm ev cihazlarını tek potada eritiyoruz
        domains = [
            "light", "switch", "fan", "climate", "cover", 
            "lock", "alarm_control_panel", "vacuum", 
            "media_player", "siren", "humidifier", "valve", "water_heater"
        ]
        all_entities = []
        for domain in domains:
            entities = await self._bridge.get_available_entities(domain)
            all_entities.extend(entities)
            
        device_map = "\n".join([f"- Name: {e['name']}, ID: {e['id']}" for e in all_entities])
        return f"Evin cihaz listesi:\n{device_map}"

    @property
    def _tools(self):
        return [{
            "type": "function",
            "function": {
                "name": "execute_service",
                "description": "Ev cihazlarını kontrol et (aç, kapat, kilit, ısıt, durdur vb.).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "domain": {"type": "string"},
                        "service": {"type": "string"},
                        "entity_id": {"type": "string"},
                        "target_name": {"type": "string"}
                    },
                    "required": ["domain", "service"]
                }
            }
        }]

    async def handle_message(self, chat_id: str, user_message: str) -> str:
        device_context = await self._get_device_context()
        system_prompt = (
            "Sen NervAI, evin tüm sistemlerini yöneten merkezi bir yapay zekasın. "
            f"Kontrol edebileceğin cihazlar:\n{device_context}\n"
            "KURALLAR:\n"
            "1. Kilit (lock) veya Alarm (alarm_control_panel) işlemleri için ASLA otomatik işlem yapma, onay iste.\n"
            "2. Klima, fan, ışık, priz (switch) ve diğer cihazlar için doğrudan 'execute_service' kullan.\n"
            "3. Cihaz ismini tam eşleştir."
        )
        
        context = [{"role": "system", "content": system_prompt}]
        raw = await self._store.build_context(chat_id)
        context.extend(raw["recent_log"])
        context.append({"role": "user", "content": user_message})

        for _ in range(5):
            response_msg = await self._provider.send_message(context, tools=self._tools)
            
            if not response_msg.tool_calls:
                final_content = response_msg.content or "Komut anlaşıldı."
                await self._store.save_turn(chat_id, user_message, final_content)
                return final_content

            context.append({"role": "assistant", "content": response_msg.content, "tool_calls": response_msg.tool_calls})
            
            for tool_call in response_msg.tool_calls:
                args = json.loads(tool_call.function.arguments)
                domain = args.get("domain", "")

                # GÜVENLİK KALKANI: Kritik cihazlar için manuel onay
                if domain in {"lock", "alarm_control_panel"}:
                    return f"'{args.get('service')}' işlemi güvenlik onayı gerektiriyor. Yapmamı onaylıyor musun?"
                
                result = await self._bridge.execute_service(**args)
                context.append({"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps(result)})

        return "Cihazı bulamadım veya işlem başarısız."