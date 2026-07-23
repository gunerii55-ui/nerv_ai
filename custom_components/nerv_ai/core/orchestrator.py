import logging
import json
import asyncio
import hashlib
from datetime import datetime, timezone
from homeassistant.util import dt as dt_util
from homeassistant.components.homeassistant.exposed_entities import async_should_expose
from homeassistant.helpers import entity_registry as er

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
        self._pending_aliases = {}

    def create_pending_alias(self, chat_id: str, entity_id: str, suggested_name: str) -> str:
        action_id = hashlib.shake_128(entity_id.encode()).hexdigest(4)
        self._pending_aliases.setdefault(chat_id, []).append({
            "id": action_id,
            "entity_id": entity_id,
            "suggested": suggested_name,
            "state": "waiting_button"
        })
        return action_id

    async def _apply_alias(self, entity_id: str, new_alias: str):
        registry = er.async_get(self._bridge.hass)
        entry = registry.async_get(entity_id)
        if entry:
            existing = set(entry.aliases) if entry.aliases else set()
            existing.add(new_alias)
            registry.async_update_entity(entity_id, aliases=existing)

    @property
    def _tools(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "execute_service",
                    "description": (
                        "Cihazı kontrol et. UYARI: entity_id'yi ASLA uydurma. "
                        "Önce search_devices veya get_entity_state ile gerçek entity_id'yi bul, "
                        "ardından execute_service'i çağır."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "domain": {"type": "string", "enum": VALID_DOMAINS},
                            "service": {"type": "string"},
                            "entity_id": {"type": "string"},
                            "service_data": {"type": "object"},
                        },
                        "required": ["domain", "service"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_devices",
                    "description": "Domain bazlı gerçek entity_id'leri listele.",
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
                    "name": "set_entity_alias",
                    "description": "Bir cihaza kullanıcının söylediği takma adı (alias) atar.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "entity_id": {"type": "string"},
                            "alias": {"type": "string"}
                        },
                        "required": ["entity_id", "alias"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "save_fact",
                    "description": "Kullanıcı rutinini/tercihini hafızaya kaydet.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "category": {"type": "string", "enum": ["routine", "preference", "general"]},
                            "fact_text": {"type": "string"},
                            "fact_key": {"type": "string"}
                        },
                        "required": ["category", "fact_text", "fact_key"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_usage_report",
                    "description": (
                        "Kullanıcının son 7 gündeki cihaz kullanım eylemlerini getirir. "
                        "Sonuç boş (empty list) dönerse, henüz yeterli kullanım verisi birikmediğini kullanıcıya nazikçe belirt."
                    ),
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_unused_entities",
                    "description": "Sistemde var olan ama daha önce hiç kullanılmayan cihazları tespit eder.",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]

    async def handle_message(self, chat_id: str, user_message: str):
        # 1. Check for Pending Alias Free-Text Input
        pending_list = self._pending_aliases.get(chat_id, [])
        active_alias = next((a for a in pending_list if a.get("state") == "waiting_text"), None)
        
        if active_alias and ":" not in user_message:
            new_alias = user_message.strip()
            await self._apply_alias(active_alias.get("entity_id"), new_alias)
            self._pending_aliases[chat_id].remove(active_alias)
            if not self._pending_aliases[chat_id]:
                del self._pending_aliases[chat_id]
            return {"text": f"✅ '{new_alias}' takma adı başarıyla cihaza atandı."}

        # 2. Check for Button Callbacks
        if ":" in user_message:
            intent, action_id = user_message.split(":", 1)
            
            # Alias Callbacks
            if intent in ["approve_alias", "custom_alias", "cancel_alias"]:
                alias_list = self._pending_aliases.get(chat_id, [])
                alias_action = next((a for a in alias_list if a.get("id") == action_id), None)
                
                if not alias_action:
                    return {"text": "⚠️ Bu istek artık geçerli değil (zaman aşımı veya yeniden başlatma). Lütfen işlemi tekrar dener misiniz?"}
                
                if intent == "approve_alias":
                    await self._apply_alias(alias_action.get("entity_id"), alias_action.get("suggested"))
                    self._pending_aliases[chat_id].remove(alias_action)
                    if not self._pending_aliases[chat_id]:
                        del self._pending_aliases[chat_id]
                    return {"text": f"✅ Önerilen '{alias_action.get('suggested')}' takma adı başarıyla kaydedildi."}
                
                elif intent == "custom_alias":
                    # Lock resolution: Reset any existing waiting_text in this chat queue to button state
                    for a in alias_list:
                        if a.get("state") == "waiting_text":
                            a["state"] = "waiting_button"
                    alias_action["state"] = "waiting_text"
                    return {"text": f"Lütfen `{alias_action.get('entity_id')}` için kullanmak istediğiniz özel ismi yazın:"}
                
                elif intent == "cancel_alias":
                    self._pending_aliases[chat_id].remove(alias_action)
                    if not self._pending_aliases[chat_id]:
                        del self._pending_aliases[chat_id]
                    return {"text": "❌ Takma ad atama işlemi yoksayıldı."}

            # Action Confirmation Callbacks
            elif intent in ["confirm_action", "cancel_action"]:
                actions = self._pending_actions.get(chat_id, [])
                action = next((a for a in actions if a.get('id') == action_id), None)

                if not action:
                    return {"text": "⚠️ Bu işlem artık geçerli değil. Lütfen tekrar dener misiniz?"}

                if intent == "confirm_action":
                    res = await self._bridge.execute_service(
                        action.get('domain'), 
                        action.get('service'), 
                        action.get('entity_id'), 
                        action.get('service_data', {})
                    )
                    self._pending_actions[chat_id].remove(action)
                    status_text = f"✅ İşlem onaylandı, sonuç: {res.get('status', 'tamamlandı')}"
                    await self._store.log_action(chat_id, action.get('entity_id'), action.get('domain'), action.get('service'), res.get('status', 'ok'))
                else:
                    self._pending_actions[chat_id].remove(action)
                    status_text = "❌ İşlem iptal edildi."
                
                if not self._pending_actions[chat_id]:
                    del self._pending_actions[chat_id]
                    
                return {"text": status_text}

        # 3. Standard LLM Flow
        raw = await self._store.build_context(chat_id)
        system_prompt = f"Sen NervAI. Rutinleri 'save_fact' ile kaydet.\n{raw.get('facts', '')}"
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
                    await self._store.save_fact(chat_id, args.get("category"), args.get("fact_text"), args.get("fact_key"))
                    res = {"status": "ok"}
                elif name == "search_devices":
                    res = await self._bridge.get_available_entities(args.get("domain", ""), args.get("search"))
                elif name == "set_entity_alias":
                    await self._apply_alias(args.get("entity_id"), args.get("alias"))
                    res = {"status": "ok"}
                elif name == "get_usage_report":
                    raw_logs = await self._store.get_usage_report(chat_id)
                    formatted_logs = []
                    for log in raw_logs:
                        try:
                            dt_naive = datetime.strptime(log["created_at"], "%Y-%m-%d %H:%M:%S")
                            dt_aware_utc = dt_naive.replace(tzinfo=timezone.utc)
                            dt_local = dt_util.as_local(dt_aware_utc)
                            log["created_at"] = dt_local.strftime("%Y-%m-%d %H:%M:%S")
                        except Exception as e:
                            _LOGGER.error(f"Zaman dönüştürme hatası: {e}")
                        formatted_logs.append(log)
                    res = {"status": "ok", "data": formatted_logs}
                elif name == "get_unused_entities":
                    used_entities = await self._store.get_used_entities(chat_id)
                    exposed = [
                        e.entity_id for e in self._bridge.hass.states.async_all() 
                        if e.domain in VALID_DOMAINS and async_should_expose(self._bridge.hass, "conversation", e.entity_id)
                    ]
                    unused = list(set(exposed) - used_entities)
                    res = {"status": "ok", "unused_entities": unused}
                elif name == "execute_service":
                    entity_id = args.get("entity_id")
                    real_domain = entity_id.split(".")[0] if entity_id else args.get("domain", "")

                    if real_domain in {"lock", "alarm_control_panel"}:
                        action_id = hashlib.shake_128(json.dumps(args).encode()).hexdigest(4)
                        pending_action = {**args, "id": action_id}
                        self._pending_actions.setdefault(chat_id, []).append(pending_action)
                        res = {"status": "pending_confirmation", "action_id": action_id}
                    else:
                        res = await self._bridge.execute_service(
                            args.get("domain", ""), 
                            args.get("service", ""), 
                            entity_id, 
                            args.get("service_data", {})
                        )
                        if entity_id:
                            await self._store.log_action(chat_id, entity_id, args.get("domain", ""), args.get("service", ""), res.get("status", "unknown"))
                else:
                    res = {"status": "error"}
                
                context.append({"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps(res)})

            if pending_action:
                return {
                    "text": f"⚠️ '{pending_action.get('service')}' işlemi onay gerektiriyor.",
                    "buttons": [
                        {"text": "✅ Onayla", "data": f"confirm_action:{pending_action.get('id')}"},
                        {"text": "❌ İptal", "data": f"cancel_action:{pending_action.get('id')}"}
                    ]
                }
        return {"text": "İşlemi tamamlayamadım."}