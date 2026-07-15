import logging
import json
import asyncio

_LOGGER = logging.getLogger(__name__)

class ConversationOrchestrator:
    def __init__(self, store, provider, bridge):
        self._store = store
        self._provider = provider
        self._bridge = bridge

    @property
    def _tools(self):
        """Tüm cihazlar için generic tool tanımı."""
        return [{
            "type": "function",
            "function": {
                "name": "execute_service",
                "description": "Evdeki herhangi bir cihazı kontrol et (ışık, klima, kilit, vs.).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "domain": {"type": "string"},
                        "service": {"type": "string"},
                        "entity_id": {"type": "string"},
                        "service_data": {"type": "object"}
                    },
                    "required": ["domain", "service"]
                }
            }
        }]

    async def _get_device_context(self):
        domains = ["light", "switch", "fan", "climate", "cover", "lock", "alarm_control_panel", "vacuum", "media_player"]
        all_entities = []
        for domain in domains:
            entities = await self._bridge.get_available_entities(domain)
            all_entities.extend(entities)
        return "\n".join([f"- Name: {e['name']}, ID: {e['id']}" for e in all_entities])

    async def handle_message(self, chat_id: str, user_message: str) -> str:
        device_context = await self._get_device_context()
        system_prompt = (
            f"Sen NervAI, ev asistanısın. Şu cihazları yönetebilirsin:\n{device_context}\n"
            "KURALLAR: Kilit/Alarm için onay al. Diğerlerini execute_service ile yönet."
        )
        
        context = [{"role": "system", "content": system_prompt}]
        raw = await self._store.build_context(chat_id)
        context.extend(raw["recent_log"])
        context.append({"role": "user", "content": user_message})

        for _ in range(5):
            response = await self._provider.send_message(context, tools=self._tools)
            if not response.tool_calls:
                final = response.content or "Anlaşıldı."
                await self._store.save_turn(chat_id, user_message, final)
                return final

            context.append({"role": "assistant", "content": response.content, "tool_calls": response.tool_calls})
            for tool_call in response.tool_calls:
                args = json.loads(tool_call.function.arguments)
                domain, service = args.pop("domain"), args.pop("service")
                entity_id = args.pop("entity_id", None)
                # Kalan tüm args -> service_data (TypeError'u çözer)
                service_data = args 
                
                if domain in {"lock", "alarm_control_panel"}:
                    return f"'{service}' işlemi onay gerektiriyor. Yapmamı onaylıyor musun?"
                
                result = await self._bridge.execute_service(domain, service, entity_id, service_data)
                context.append({"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps(result)})

        return "İşlem tamamlanamadı."