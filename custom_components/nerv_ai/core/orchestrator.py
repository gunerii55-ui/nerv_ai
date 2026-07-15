import logging, json
from typing import Any

_LOGGER = logging.getLogger(__name__)

class ConversationOrchestrator:
    def __init__(self, store: Any, provider: Any, bridge: Any):
        self._store = store
        self._provider = provider
        self._bridge = bridge

    @property
    def _tools(self):
        return [{
            "type": "function",
            "function": {
                "name": "execute_service",
                "description": "Cihazı kesin biliyorsan entity_id, ismini biliyorsan target_name kullan.",
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
        context = []
        raw = await self._store.build_context(chat_id)
        if raw["facts"]:
            context.append({"role": "system", "content": "\n".join([f"{f['key']}: {f['value']}" for f in raw["facts"]])})
        
        context.extend(raw["recent_log"])
        context.append({"role": "user", "content": user_message})

        for _ in range(5):  # MAX_TOOL_CALLS_PER_TURN limitli Recursive Loop
            response_msg = await self._provider.send_message(context, tools=self._tools)
            
            # Tool çağrısı yoksa döngüyü bitir, cevabı veritabanına kaydet ve kullanıcıya dön
            if not response_msg.tool_calls:
                final_reply = response_msg.content or ""
                await self._store.save_turn(chat_id, user_message, final_reply)
                return final_reply

            # Asistanın tool çağrısını bağlama ekle
            context.append({"role": "assistant", "content": response_msg.content, "tool_calls": response_msg.tool_calls})
            
            for tool_call in response_msg.tool_calls:
                args = json.loads(tool_call.function.arguments)
                
                # Güvenlik Kalkanı
                if args.get("domain") in {"lock", "alarm_control_panel"}:
                    return f"'{args.get('service')}' işlemi onay gerektiriyor, henüz otomatik çalıştırmıyorum."
                
                result = await self._bridge.execute_service(**args)
                context.append({
                    "role": "tool", 
                    "tool_call_id": tool_call.id, 
                    "content": json.dumps(result)
                })

        return "İşlemi tamamlayamadım, çok fazla adım gerekti."