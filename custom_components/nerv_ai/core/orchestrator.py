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
        """LLM'in kullanabileceği araçları tanımlar."""
        return [{
            "type": "function",
            "function": {
                "name": "execute_service",
                "description": "Işıkları veya cihazları aç/kapat.",
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

    async def _get_device_context(self):
        entities = await self._bridge.get_available_entities("light")
        device_map = "\n".join([f"- Name: {e['name']}, ID: {e['id']}" for e in entities])
        return f"Evdeki ışıklar listesi:\n{device_map}"

    async def handle_message(self, chat_id: str, user_message: str) -> str:
        device_context = await self._get_device_context()
        system_prompt = (
            "Sen NervAI, ev asistanısın. Aşağıdaki ışık listesini kullanarak komutları uygula. "
            f"{device_context}\n"
            "Kullanıcı bir ışık açmak/kapatmak isterse, listeden doğru entity_id'yi bul ve kullan."
        )
        
        context = [{"role": "system", "content": system_prompt}]
        raw = await self._store.build_context(chat_id)
        context.extend(raw["recent_log"])
        context.append({"role": "user", "content": user_message})

        # Tool kullanımı için 5 adımlı döngü (Recursive loop)
        for _ in range(5):
            response_msg = await self._provider.send_message(context, tools=self._tools)
            
            if not response_msg.tool_calls:
                final_content = response_msg.content or "Anladım."
                await self._store.save_turn(chat_id, user_message, final_content)
                return final_content

            context.append({"role": "assistant", "content": response_msg.content, "tool_calls": response_msg.tool_calls})
            
            for tool_call in response_msg.tool_calls:
                args = json.loads(tool_call.function.arguments)
                
                # Güvenlik Kalkanı
                if args.get("domain") in {"lock", "alarm_control_panel"}:
                    return f"'{args.get('service')}' işlemi onay gerektiriyor."
                
                result = await self._bridge.execute_service(**args)
                context.append({
                    "role": "tool", 
                    "tool_call_id": tool_call.id, 
                    "content": json.dumps(result)
                })

        return "İşlemi tamamlayamadım."