import logging
import json
import asyncio

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
                    "description": "Cihazı kontrol et.",
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
                    "description": "Domain bazlı cihaz listesini getir. domain mutlaka HA domain adı olmalı (İngilizce, örn: kapı/panjur/garaj için 'cover', kilit için 'lock').",
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
        ]

    async def handle_message(self, chat_id: str, user_message: str) -> str:
        msg = user_message.strip().lower()

        # KRİTİK #1: Onay Hafızası
        if chat_id in self._pending_actions:
            if msg in {"evet", "onaylıyorum", "yes", "tamam"}:
                action = self._pending_actions.pop(chat_id)
                res = await self._bridge.execute_service(**action)
                return f"İşlem onaylandı, sonuç: {res.get('status')}"
            else:
                self._pending_actions.pop(chat_id)
                return "İşlem iptal edildi."

        context = [{"role": "system", "content": "Sen NervAI. Domain bazlı ara, Kilit/Alarm için onay al."}]
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

            pending_confirmation = None

            for tool_call in response.tool_calls:
                args = json.loads(tool_call.function.arguments)
                name = tool_call.function.name

                if name == "get_entity_state":
                    res = await self._bridge.get_state(args.get("entity_id"))

                elif name == "search_devices":
                    domain_arg = args.get("domain")
                    search_arg = args.get("search")
                    res = await self._bridge.get_available_entities(domain_arg, search_arg)
                    _LOGGER.warning("NervAI DEBUG: search_devices domain='%s' search='%s' -> %d sonuç: %s", domain_arg, search_arg, len(res), res)

                elif name == "execute_service":
                    entity_id = args.get("entity_id")
                    real_domain = entity_id.split(".")[0] if entity_id else args.get("domain")

                    if real_domain in {"lock", "alarm_control_panel"}:
                        pending_confirmation = {
                            "domain": args.get("domain"),
                            "service": args.get("service"),
                            "entity_id": entity_id,
                            "service_data": args.get("service_data") or {},
                        }
                        res = {"status": "pending_confirmation"}
                    else:
                        res = await self._bridge.execute_service(
                            args.get("domain"), args.get("service"), entity_id, args.get("service_data") or {}
                        )
                else:
                    res = {"status": "error", "message": f"Bilinmeyen araç: {name}"}

                context.append({"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps(res)})

            if pending_confirmation:
                self._pending_actions[chat_id] = pending_confirmation
                return f"'{pending_confirmation['service']}' işlemi onay gerektiriyor. Onaylıyor musunuz? (evet/hayır)"

        return "İşlemi tamamlayamadım, çok fazla adım gerekti."