import logging
import json
import asyncio
import hashlib

_LOGGER = logging.getLogger(__name__)

VALID_DOMAINS = [
    "light", "switch", "cover", "lock", "climate", "fan",
    "alarm_control_panel", "media_player", "vacuum",
    "sensor", "binary_sensor", "camera",
]

class ConversationOrchestrator:
    def __init__(self, store, provider, bridge):
        self._store, self._provider, self._bridge = store, provider, bridge
        self._pending_actions = {}

    @property
    def _tools(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "execute_service",
                    "description": (
                        "Cihazı kontrol et. Servis adı domain'e göre değişir: "
                        "light/switch/fan için 'turn_on'/'turn_off'; "
                        "cover (kapı, garaj, panjur) için 'open_cover'/'close_cover'/'stop_cover' "
                        "(ASLA 'open'/'close' değil); lock için 'lock'/'unlock'; "
                        "climate için 'set_temperature'."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "domain": {"type": "string", "enum": VALID_DOMAINS},
                            "service": {"type": "string"},
                            "entity_id": {"type": "string"},
                            "service_data": {"type": "object"},
                        },
                        "required": ["domain", "service", "entity_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_entity_state",
                    "description": "Sensör/cihaz durumunu oku.",
                    "parameters": {
                        "type": "object",
                        "properties": {"entity_id": {"type": "string"}},
                        "required": ["entity_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_devices",
                    "description": "Domain bazlı cihaz listesini getir.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "domain": {"type": "string", "enum": VALID_DOMAINS},
                            "search": {"type": "string"}
                        },
                        "required": ["domain"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "save_fact",
                    "description": "Kullanıcının rutinini/tercihini kaydet.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "category": {"type": "string", "enum": ["routine", "preference", "general"]},
                            "fact_text": {"type": "string"},
                            "fact_key": {"type": "string", "description": "Benzersiz tanımlayıcı (örn: 'morning_routine')"}
                        },
                        "required": ["category", "fact_text", "fact_key"],
                    },
                },
            },
        ]

    async def handle_message(self, chat_id: str, user_message: str):
        msg = user_message.strip().lower()

        # Onay Mekanizması (Multi-Pending + Hash ID)
        if ":" in msg and (msg.startswith("confirm_action") or msg.startswith("cancel_action")):
            intent, action_id = msg.split(":")
            actions = self._pending_actions.get(chat_id, [])
            action = next((a for a in actions if a['id'] == action_id), None)

            if not action:
                return {"text": "⚠️ Bu işlem artık geçerli değil (zaman aşımı veya sistem yeniden başladı)."}

            if intent == "confirm_action":
                res = await self._bridge.execute_service(
                    action['domain'], action['service'], action['entity_id'], action['service_data']
                )
                self._pending_actions[chat_id].remove(action)
                return {"text": f"✅ İşlem onaylandı, sonuç: {res.get('status')}"}
            else:
                self._pending_actions[chat_id].remove(action)
                return {"text": "❌ İşlem iptal edildi."}

        raw = await self._store.build_context(chat_id)
        system_prompt = f"Sen NervAI. Kullanıcı rutinlerini 'save_fact' ile kaydet.\n{raw.get('facts', '')}"
        context = [{"role": "system", "content": system_prompt}] + raw["recent_log"]
        context.append({"role": "user", "content": user_message})

        for _ in range(5):
            response = await self._provider.send_message(context, tools=self._tools)
            if not response.tool_calls:
                final = response.content or "Anlaşıldı."
                await self._store.save_turn(chat_id, user_message, final)
                return {"text": final}

            context.append({"role": "assistant", "content": response.content, "tool_calls": response.tool_calls})
            
            pending_action = None
            for tool_call in response.tool_calls:
                args = json.loads(tool_call.function.arguments)
                name = tool_call.function.name

                if name == "save_fact":
                    await self._store.save_fact(chat_id, args["category"], args["fact_text"], args["fact_key"])
                    res = {"status": "ok"}
                elif name == "search_devices":
                    res = await self._bridge.get_available_entities(args["domain"], args.get("search"))
                elif name == "execute_service":
                    entity_id = args.get("entity_id")
                    real_domain = entity_id.split(".")[0] if entity_id else args.get("domain")

                    if real_domain in {"lock", "alarm_control_panel"}:
                        action_id = hashlib.shake_128(json.dumps(args).encode()).hexdigest(4)
                        pending_action = {**args, "id": action_id}
                        self._pending_actions.setdefault(chat_id, []).append(pending_action)
                        res = {"status": "pending_confirmation", "action_id": action_id}
                    else:
                        res = await self._bridge.execute_service(args["domain"], args["service"], entity_id, args.get("service_data", {}))
                else:
                    res = {"status": "error"}
                
                context.append({"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps(res)})

            if pending_action:
                return {
                    "text": f"⚠️ '{pending_action['service']}' işlemi onay gerektiriyor.",
                    "buttons": [
                        {"text": "✅ Onayla", "data": f"confirm_action:{pending_action['id']}"},
                        {"text": "❌ İptal", "data": f"cancel_action:{pending_action['id']}"}
                    ]
                }

        return {"text": "İşlemi tamamlayamadım, çok fazla adım gerekti."}