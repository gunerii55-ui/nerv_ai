"""Central orchestrator connecting Channels, Memory, and LLM."""
import logging
import json
from typing import Any
from custom_components.nerv_ai.providers.base import LLMProvider

_LOGGER = logging.getLogger(__name__)

class ConversationOrchestrator:
    def __init__(self, store: Any, provider: LLMProvider, bridge: Any):
        self._store = store
        self._provider = provider
        self._bridge = bridge

    @property
    def _tools(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_available_entities",
                    "description": "Home Assistant'taki cihazları (entity) domain bazında listeler.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "domain": {"type": "string", "description": "Örn: light, switch, climate, sensor"}
                        },
                        "required": ["domain"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "execute_service",
                    "description": "Home Assistant servisini çalıştırarak cihazları kontrol eder.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "domain": {"type": "string"},
                            "service": {"type": "string", "description": "Örn: turn_on, turn_off, set_temperature"},
                            "entity_id": {"type": "string"},
                            "data": {"type": "object", "description": "Ek servis parametreleri"}
                        },
                        "required": ["domain", "service", "entity_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "save_fact",
                    "description": "Kullanıcı tercihlerini veya kimlik bilgilerini kalıcı hafızaya yazar.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "key": {"type": "string"},
                            "value": {"type": "string"}
                        },
                        "required": ["key", "value"]
                    }
                }
            }
        ]

    async def handle_message(self, chat_id: str, user_message: str) -> str:
        # 1. Hafızayı Getir
        raw_context = await self._store.build_context(chat_id)
        
        # 2. Runtime Context Hazırla
        context_to_send = []
        if raw_context["facts"]:
            facts_str = "\n".join([f"{f['key']}: {f['value']}" for f in raw_context["facts"]])
            context_to_send.append({"role": "system", "content": f"Bildiğin kesin kurallar:\n{facts_str}"})
            
        context_to_send.extend(raw_context["recent_log"])
        context_to_send.append({"role": "user", "content": user_message})
        
        # 3. Tool-Call Döngüsü (Sonsuz döngü kalkanı için limit: 5)
        for _ in range(5):
            try:
                response_msg = await self._provider.send_message(context_to_send, tools=self._tools)
            except Exception as e:
                _LOGGER.error("NervAI: LLM Provider error: %s", e)
                return "Sistem hatası: Yapay zeka sağlayıcısına ulaşılamadı."

            # Asistanın cevabını (tool call dahil) context'e ekle
            context_to_send.append(response_msg.model_dump(exclude_none=True))

            # Tool Call yoksa, final metni dön
            if not response_msg.tool_calls:
                final_reply = response_msg.content or ""
                await self._store.save_turn(chat_id, user_message, final_reply)
                return final_reply

            # Tool Call var, işlemleri yap
            for tool_call in response_msg.tool_calls:
                func_name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)
                result_str = ""
                
                try:
                    if func_name == "get_available_entities":
                        result = await self._bridge.get_available_entities(args.get("domain"))
                        result_str = json.dumps(result)
                    elif func_name == "execute_service":
                        result = await self._bridge.execute_service(
                            args.get("domain"), args.get("service"), 
                            args.get("entity_id"), args.get("data")
                        )
                        result_str = json.dumps(result)
                    elif func_name == "save_fact":
                        await self._store.save_fact(chat_id, args.get("key"), args.get("value"))
                        result_str = '{"status": "ok", "message": "Fact saved permanently."}'
                    else:
                        result_str = f'{{"status": "error", "message": "Unknown function {func_name}"}}'
                except Exception as e:
                    _LOGGER.error("Tool execution error: %s", e)
                    result_str = json.dumps({"status": "error", "message": str(e)})

                # Tool sonucunu context'e ekle ve döngü başa sarsın
                context_to_send.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result_str
                })

        return "Hata: Cihaz işlem limiti aşıldı, komut tamamlanamadı."
