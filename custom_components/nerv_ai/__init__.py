import logging
import asyncio
import os
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.components.homeassistant.exposed_entities import async_should_expose
from homeassistant.components import panel_custom, websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import config_validation as cv
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
PLATFORMS = []


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Entegrasyonun global ve panel/websocket kayıt hazırlığı."""
    hass.data.setdefault(DOMAIN, {})

    frontend_path = hass.config.path("custom_components/nerv_ai/frontend")
    if os.path.exists(frontend_path):
        await hass.http.async_register_static_paths([
            StaticPathConfig("/nervai_static", frontend_path, cache_headers=False)
        ])

    await panel_custom.async_register_panel(
        hass,
        frontend_url_path="nervai",
        webcomponent_name="nervai-panel",
        sidebar_title="NervAI Yönetim",
        sidebar_icon="mdi:robot-outline",
        require_admin=True,
        module_url="/nervai_static/panel.js?v=99",
        config={}
    )

    websocket_api.async_register_command(hass, ws_get_entities)
    websocket_api.async_register_command(hass, ws_set_alias)
    websocket_api.async_register_command(hass, ws_get_facts)
    websocket_api.async_register_command(hass, ws_delete_fact)
    websocket_api.async_register_command(hass, ws_get_config)
    websocket_api.async_register_command(hass, ws_set_config)
    websocket_api.async_register_command(hass, ws_reset_chat)
    websocket_api.async_register_command(hass, ws_update_fact)
    websocket_api.async_register_command(hass, ws_cleanup_bad_aliases)
    websocket_api.async_register_command(hass, ws_clear_all_facts)

    return True


def _get_store(hass):
    domain_data = hass.data.get(DOMAIN, {})
    for key, val in domain_data.items():
        if isinstance(val, dict) and "store" in val:
            return val["store"]
    return None


def _get_active_entry(hass):
    entries = hass.config_entries.async_entries(DOMAIN)
    return entries[0] if entries else None


class HABridgeImpl:
    def __init__(self, hass: HomeAssistant):
        self.hass = hass

    async def get_available_entities(self, domain: str, search: str = None) -> list[dict]:
        states = self.hass.states.async_all(domain)
        exposed = [
            {
                "id": s.entity_id,
                "name": s.attributes.get("friendly_name", s.entity_id),
            }
            for s in states
            if async_should_expose(self.hass, "conversation", s.entity_id)
        ]

        if not search:
            return exposed

        filtered = [
            e
            for e in exposed
            if search.lower() in e["name"].lower()
            or search.lower() in e["id"].lower()
        ]

        return filtered if filtered else exposed

    async def execute_service(
        self,
        domain,
        service,
        entity_id=None,
        service_data=None,
    ):
        if not entity_id:
            return {
                "status": "error",
                "message": "entity_id eksik, önce search_devices ile gerçek entity_id'yi bul.",
            }

        if not self.hass.states.get(entity_id):
            return {
                "status": "error",
                "message": f"'{entity_id}' isimli bir cihaz sistemde bulunamadı.",
            }

        if not self.hass.services.has_service(domain, service):
            valid_services = list(
                self.hass.services.async_services().get(domain, {}).keys()
            )
            return {
                "status": "error",
                "message": f"'{domain}.{service}' diye bir servis yok. '{domain}' domaini için geçerli servisler: {valid_services}. Bunlardan birini kullan.",
            }

        data = service_data or {}
        data["entity_id"] = entity_id

        try:
            await self.hass.services.async_call(
                domain,
                service,
                service_data=data,
                blocking=True,
            )
            return {"status": "ok"}
        except Exception as e:
            _LOGGER.error(f"Service Call Error: {e}")
            return {"status": "error", "message": str(e)}

    async def get_state(self, entity_id):
        state = self.hass.states.get(entity_id)
        return (
            {"state": state.state, "attributes": dict(state.attributes)}
            if state
            else {"error": "Not found"}
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    from .channels.telegram import TelegramBot
    from .core.orchestrator import ConversationOrchestrator
    from .core.proactive import ProactiveManager
    from .memory.store import MemoryStore
    from .providers.openai import OpenAIProvider
    import aiosqlite

    hass.data.setdefault(DOMAIN, {})

    db = await aiosqlite.connect(
        hass.config.path(f".storage/nerv_ai_{entry.entry_id}.db")
    )

    bridge = HABridgeImpl(hass)

    store = MemoryStore(
        db=db,
        db_lock=asyncio.Lock(),
    )
    await store.async_init_db()

    orchestrator = ConversationOrchestrator(
        store=store,
        provider=OpenAIProvider(
            api_key=entry.data.get("openai_api_key")
        ),
        bridge=bridge,
    )

    bot = TelegramBot(
        token=entry.data.get("telegram_token"),
        ha_bridge=bridge,
        orchestrator=orchestrator,
    )

    proactive = ProactiveManager(hass, bot, store)
    await proactive.setup_monitoring()

    hass.data[DOMAIN][entry.entry_id] = {
        "db": db,
        "store": store,
        "telegram_bot": bot,
        "proactive": proactive,
    }

    hass.async_create_background_task(
        bot.initialize_and_start(),
        name="NervAI_Telegram_Polling",
    )

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> bool:
    data = hass.data[DOMAIN].get(entry.entry_id)

    if not data:
        return True

    if "proactive" in data:
        data["proactive"].unload()

    bot = data.get("telegram_bot")

    if bot and bot.app:
        try:
            if bot.app.updater and bot.app.updater.running:
                await asyncio.wait_for(
                    bot.app.updater.stop(),
                    timeout=10,
                )

            if bot.app.running:
                await asyncio.wait_for(
                    bot.app.stop(),
                    timeout=10,
                )

            await bot.app.shutdown()

        except asyncio.TimeoutError:
            _LOGGER.warning(
                "NervAI: Telegram app shutdown timed out"
            )

    if "db" in data:
        await data["db"].close()

    hass.data[DOMAIN].pop(entry.entry_id)

    return True


# --- WebSocket Handlers ---

@websocket_api.websocket_command({vol.Required("type"): "nervai/get_entities"})
@websocket_api.async_response
async def ws_get_entities(hass, connection, msg):
    if not connection.user.is_admin:
        connection.send_error(msg["id"], "unauthorized", "Admin yetkisi gerekli.")
        return
    registry = er.async_get(hass)
    entities_data = []
    for state in hass.states.async_all():
        entry = registry.async_get(state.entity_id)
        entities_data.append({
            "entity_id": state.entity_id,
            "name": state.name,
            "domain": state.domain,
            "area": entry.area_id if entry else None,
            "aliases": list(entry.aliases) if entry and entry.aliases else []
        })
    connection.send_result(msg["id"], entities_data)


@websocket_api.websocket_command({
    vol.Required("type"): "nervai/set_alias",
    vol.Required("entity_id"): cv.entity_id,
    vol.Required("aliases"): [cv.string]
})
@websocket_api.async_response
async def ws_set_alias(hass, connection, msg):
    if not connection.user.is_admin:
        connection.send_error(msg["id"], "unauthorized", "Admin yetkisi gerekli.")
        return
    registry = er.async_get(hass)
    entry = registry.async_get(msg["entity_id"])
    if entry:
        registry.async_update_entity(msg["entity_id"], aliases=set(msg["aliases"]))
        connection.send_result(msg["id"], {"success": True})
    else:
        connection.send_error(msg["id"], "entity_not_found", "Entity bulunamadı.")


@websocket_api.websocket_command({vol.Required("type"): "nervai/get_facts"})
@websocket_api.async_response
async def ws_get_facts(hass, connection, msg):
    if not connection.user.is_admin:
        connection.send_error(msg["id"], "unauthorized", "Admin yetkisi gerekli.")
        return
    store = _get_store(hass)
    if not store:
        connection.send_result(msg["id"], [])
        return
    chat_id = await store.get_config("authorized_chat_id")
    facts = await store.get_facts_list(chat_id) if chat_id else []
    connection.send_result(msg["id"], facts)


@websocket_api.websocket_command({
    vol.Required("type"): "nervai/delete_fact",
    vol.Required("fact_key"): cv.string
})
@websocket_api.async_response
async def ws_delete_fact(hass, connection, msg):
    if not connection.user.is_admin:
        connection.send_error(msg["id"], "unauthorized", "Admin yetkisi gerekli.")
        return
    store = _get_store(hass)
    if not store:
        connection.send_error(msg["id"], "no_store", "Store bulunamadı.")
        return
    chat_id = await store.get_config("authorized_chat_id")
    if chat_id:
        await store.forget_fact(chat_id, msg["fact_key"])
        connection.send_result(msg["id"], {"success": True})
    else:
        connection.send_error(msg["id"], "no_chat_id", "Aktif chat_id bulunamadı.")


@websocket_api.websocket_command({vol.Required("type"): "nervai/get_config"})
@websocket_api.async_response
async def ws_get_config(hass, connection, msg):
    if not connection.user.is_admin:
        connection.send_error(msg["id"], "unauthorized", "Admin yetkisi gerekli.")
        return
    entry = _get_active_entry(hass)
    conf = {
        "model": entry.data.get("model", "gpt-4o") if entry else "gpt-4o",
        "token": "sk-masked",
        "telegram_token": "tg-masked"
    }
    connection.send_result(msg["id"], conf)


@websocket_api.websocket_command({
    vol.Required("type"): "nervai/set_config",
    vol.Required("model"): cv.string,
    vol.Required("token"): cv.string,
    vol.Required("telegram_token"): cv.string,
})
@websocket_api.async_response
async def ws_set_config(hass, connection, msg):
    if not connection.user.is_admin:
        connection.send_error(msg["id"], "unauthorized", "Admin yetkisi gerekli.")
        return
    entry = _get_active_entry(hass)
    if entry:
        new_data = {
            **entry.data,
            "model": msg["model"]
        }
        if msg["token"] != "sk-masked":
            new_data["openai_api_key"] = msg["token"]
        if msg["telegram_token"] != "tg-masked":
            new_data["telegram_token"] = msg["telegram_token"]
            
        hass.config_entries.async_update_entry(entry, data=new_data)
        await hass.config_entries.async_reload(entry.entry_id)
        
    connection.send_result(msg["id"], {"success": True})


@websocket_api.websocket_command({vol.Required("type"): "nervai/reset_chat"})
@websocket_api.async_response
async def ws_reset_chat(hass, connection, msg):
    if not connection.user.is_admin:
        connection.send_error(msg["id"], "unauthorized", "Admin yetkisi gerekli.")
        return
    store = _get_store(hass)
    if store:
        await store.delete_config("authorized_chat_id")
    connection.send_result(msg["id"], {"success": True})


@websocket_api.websocket_command({
    vol.Required("type"): "nervai/update_fact",
    vol.Required("fact_key"): cv.string,
    vol.Required("category"): cv.string,
    vol.Required("fact_text"): cv.string,
})
@websocket_api.async_response
async def ws_update_fact(hass, connection, msg):
    if not connection.user.is_admin:
        connection.send_error(msg["id"], "unauthorized", "Admin yetkisi gerekli.")
        return
    store = _get_store(hass)
    chat_id = await store.get_config("authorized_chat_id") if store else None
    if store and chat_id:
        await store.save_fact(chat_id, msg["category"], msg["fact_text"], msg["fact_key"])
        connection.send_result(msg["id"], {"success": True})
    else:
        connection.send_error(msg["id"], "no_chat_id", "Aktif chat_id bulunamadı.")


@websocket_api.websocket_command({vol.Required("type"): "nervai/cleanup_bad_aliases"})
@websocket_api.async_response
async def ws_cleanup_bad_aliases(hass, connection, msg):
    if not connection.user.is_admin:
        connection.send_error(msg["id"], "unauthorized", "Admin yetkisi gerekli.")
        return
    
    registry = er.async_get(hass)
    cleaned_count = 0
    
    for entity_id, entry in registry.entities.items():
        if entry.aliases and "0" in entry.aliases:
            cleaned_aliases = set(entry.aliases) - {"0"}
            registry.async_update_entity(entity_id, aliases=cleaned_aliases)
            cleaned_count += 1
            
    connection.send_result(msg["id"], {"success": True, "cleaned_count": cleaned_count})


@websocket_api.websocket_command({vol.Required("type"): "nervai/clear_all_facts"})
@websocket_api.async_response
async def ws_clear_all_facts(hass, connection, msg):
    if not connection.user.is_admin:
        connection.send_error(msg["id"], "unauthorized", "Admin yetkisi gerekli.")
        return
    store = _get_store(hass)
    chat_id = await store.get_config("authorized_chat_id") if store else None
    if store and chat_id:
        await store.clear_all_facts(chat_id)
        connection.send_result(msg["id"], {"success": True})
    else:
        connection.send_error(msg["id"], "no_chat_id", "Aktif chat_id bulunamadı.")