import logging
import json
import asyncio

_LOGGER = logging.getLogger(__name__)

class ConversationOrchestrator:
    def __init__(self, store, provider, bridge):
        self._store = store
        self._provider = provider
        self._bridge = bridge
        self._pending_actions = {} # Onay bekleyen işlemler

    @property
    def _tools(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "execute_service",
                    "description": "Cihazı kontrol et (aç/kapat/kilit vb.).",
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
            },
            {
                "type": "function",
                "function": {
                    "name": "get_entity_state",
                    "description": "Sensör değerini veya cihazın mevcut durumunu oku.",
                    "parameters": {
                        "type": "object",
                        "properties": {"entity_id": {"type": "string"}},
                        "required": ["entity_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_devices",
                    "description": "İsmi verilen cihazları veya sensörleri ara.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "domain": {"type": "string"},
                            "search": {"type": "string"}
                        },
                        "required": ["domain"]
                    }
                }
            }
        ]

    async def handle_message(self, chat_id: str, user_message: str) -> str:
        msg = user_message.strip().lower()

        # 1. Onay Mekanizması (Pending Actions)
        if chat_id in self._pending_actions:
            if msg in {"evet", "onaylıyorum", "yes"}:
                action = self._pending_actions.pop(chat_id)
                res = await self._bridge.execute_service(**action)
                return f"Onaylandı, sonuç: {res.get('status')}"
            else:
                self._pending_actions.pop(chat_id)
                return "İşlem iptal edildi."

        # 2. Normal İşleme
        context = [{"role": "system", "content": "Sen NervAI. Kilit/Alarm için onay al. Cihaz listesi için search_devices kullan."}]
        raw = await self._store.build_context(chat_id)
        context.extend(raw["recent_log"])
        context.append({"role": "user", "content": user_message})

        for _ in range(3):
            response = await self._provider.send_message(context, tools=self._tools)
            if not response.tool_calls:
                final = response.content or "Anlaşıldı."
                await self._store.save_turn(chat_id, user_message, final)
                return final

            context.append({"role": "assistant", "content": response.content, "tool_calls": response.tool_calls})
            for tool_call in response.tool_calls:
                args = json.loads(tool_call.function.arguments)
                func_name = tool_call.function.name
                
                if func_name == "get_entity_state":
                    res = await self._bridge.get_state(args["entity_id"])
                    context.append({"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps(res)})
                
                elif func_name == "search_devices":
                    res = await self._bridge.get_available_entities(args["domain"], args.get("search"))
                    context.append({"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps(res)})
                
                elif func_name == "execute_service":
                    domain, service = args.pop("domain"), args.pop("service")
                    entity_id = args.pop("entity_id", None)
                    service_data = args.pop("service_data", {}) # Default {}
                    
                    if domain in {"lock", "alarm_control_panel"}:
                        self._pending_actions[chat_id] = {"domain": domain, "service": service, "entity_id": entity_id, "service_data": service_data}
                        return f"'{service}' işlemi onay gerektiriyor. Onaylıyor musun?"
                    
                    res = await self._bridge.execute_service(domain, service, entity_id, service_data)
                    context.append({"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps(res)})

        return "İşlem tamamlanamadı."