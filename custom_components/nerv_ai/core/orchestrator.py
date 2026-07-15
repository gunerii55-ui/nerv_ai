import logging
import json
import asyncio

_LOGGER = logging.getLogger(__name__)

class ConversationOrchestrator:
    def __init__(self, store, provider, bridge):
        self._store = store
        self._provider = provider
        self._bridge = bridge
        self._pending_actions = {}  # KRİTİK #1: Hafızalı onay mekanizması

    @property
    def _tools(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "execute_service",
                    "description": "Cihazı kontrol et.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "domain": {"type": "string"},
                            "service": {"type": "string"},
                            "entity_id": {"type": "string"},
                            "service_data": {"type": "object"}
                        },
                        "required": ["domain", "service", "entity_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_entity_state",
                    "description": "Sensör veya cihaz durumunu (pil, sıcaklık vb.) oku.",
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
                    "description": "Cihazları domain ve isim filtresiyle ara.",
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

        # 1. Onay Mekanizması (Stateful)
        if chat_id in self._pending_actions:
            if msg in {"evet", "onaylıyorum", "yes"}:
                action = self._pending_actions.pop(chat_id)
                res = await self._bridge.execute_service(**action)
                return f"Onaylandı, sonuç: {res.get('status')}"
            else:
                self._pending_actions.pop(chat_id)
                return "İşlem iptal edildi."

        # 2. İşleme Başla
        context = [{"role": "system", "content": "Sen NervAI. Kilit/Alarm işlemleri için onay al."}]
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
                name = tool_call.function.name
                
                # A. DURUM OKUMA (Read)
                if name == "get_entity_state":
                    res = await self._bridge.get_state(args["entity_id"])
                    context.append({"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps(res)})
                
                # B. CİHAZ ARAMA (Search)
                elif name == "search_devices":
                    res = await self._bridge.get_available_entities(args["domain"], args.get("search"))
                    context.append({"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps(res)})
                
                # C. AKSİYON (Write)
                elif name == "execute_service":
                    entity_id = args.get("entity_id", "")
                    domain = entity_id.split('.')[0] # KRİTİK #2: Deterministik domain kontrolü
                    
                    # Güvenlik Kalkanı: LLM'in tahminine değil, entity_id'nin kendisine bak
                    if domain in {"lock", "alarm_control_panel"}:
                        self._pending_actions[chat_id] = args
                        return f"'{args['service']}' işlemi onay gerektiriyor. Onaylıyor musun?"
                    
                    res = await self._bridge.execute_service(domain, args["service"], entity_id, args.get("service_data", {}))
                    context.append({"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps(res)})

        return "İşlem tamamlanamadı."