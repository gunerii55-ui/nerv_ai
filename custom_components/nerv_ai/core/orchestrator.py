import logging, json, asyncio

_LOGGER = logging.getLogger(__name__)


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
                            "domain": {"type": "string"},
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
                        "properties": {"domain": {"type": "string"}},
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

            for tool_call in response.tool_calls:
                args = json.loads(tool_call.function.arguments)
                name = tool_call.function.name

                if name == "get_entity_state":
                    res = await self._bridge.get_state(args["entity_id"])
                    context.append({"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps(res)})

                elif name == "search_devices":
                    res = await self._bridge.get_available_entities(args["domain"])
                    context.append({"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps(res)})

                elif name == "execute_service":
                    entity_id = args.get("entity_id")
                    # KRİTİK #2: Domain doğrulaması LLM'in tahminine değil,
                    # gerçek entity_id prefix'ine dayanmalı
                    real_domain = entity_id.split(".")[0] if entity_id else args.get("domain")
                elif name == "search_devices":
    res = await self._bridge.get_available_entities(args["domain"])
    _LOGGER.warning("NervAI DEBUG search_devices(%s) -> %s", args["domain"], res)
    context.append({"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps(res)})

                    if real_domain in {"lock", "alarm_control_panel"}:
                        self._pending_actions[chat_id] = {
                            "domain": args.get("domain"),
                            "service": args.get("service"),
                            "entity_id": entity_id,
                            "service_data": args.get("service_data") or {},
                        }
                        return f"'{args.get('service')}' işlemi onay gerektiriyor. Onaylıyor musunuz? (evet/hayır)"

                    res = await self._bridge.execute_service(
                        args.get("domain"), args.get("service"), entity_id, args.get("service_data") or {}
                    )
                    context.append({"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps(res)})

        return "İşlemi tamamlayamadım, çok fazla adım gerekti."