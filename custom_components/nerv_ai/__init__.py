"""The NervAI integration."""
import logging
import asyncio
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.components.homeassistant.exposed_entities import async_should_expose
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
PLATFORMS = []

class HABridgeImpl:
    def __init__(self, hass: HomeAssistant):
        self._hass = hass

    async def get_available_entities(self, domain: str, search: str | None = None, limit: int = 30) -> list[dict]:
        states = self._hass.states.async_all(domain)
        results = []
        for state in states:
            if not async_should_expose(self._hass, "conversation", state.entity_id):
                continue
            name = state.attributes.get("friendly_name", state.entity_id)
            if search and search.lower() not in name.lower() and search.lower() not in state.entity_id.lower():
                continue
            results.append({"id": state.entity_id, "name": name})
            if len(results) >= limit: break
        return results

    async def execute_service(self, domain: str, service: str, entity_id: str | None = None, target_name: str | None = None, data: dict | None = None) -> dict:
        if not entity_id and target_name:
            result = intent.async_match_targets(self._hass, intent.MatchTargetsConstraints(name=target_name, domains={domain}))
            if not result.is_match:
                return {"status": "error", "message": f"'{target_name}' bulunamadı veya belirsiz."}
            entity_id = result.matched_states[0].entity_id

        try:
            await self._hass.services.async_call(domain, service, {"entity_id": entity_id, **(data or {})}, blocking=True)
            return {"status": "ok", "message": "Service executed."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    from .channels.telegram import TelegramBot
    from .core.orchestrator import ConversationOrchestrator
    from .memory.store import MemoryStore
    from .providers.openai import OpenAIProvider
    import aiosqlite

    hass.data.setdefault(DOMAIN, {})
    db = await aiosqlite.connect(hass.config.path("nerv_ai_memory.db"))
    bridge = HABridgeImpl(hass)
    store = MemoryStore(db=db, db_lock=asyncio.Lock())
    await store.async_init_db()
    
    orchestrator = ConversationOrchestrator(store=store, provider=OpenAIProvider(api_key=entry.data.get("openai_api_key")), bridge=bridge)
    bot = TelegramBot(token=entry.data.get("telegram_token"), ha_bridge=bridge, orchestrator=orchestrator)

    # bot.app yerine bot'un kendisini kaydediyoruz
    hass.data[DOMAIN][entry.entry_id] = {"db": db, "telegram_bot": bot}
    hass.async_create_background_task(bot.initialize_and_start(), name="NervAI_Telegram_Polling")
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    data = hass.data[DOMAIN].get(entry.entry_id)
    if not data:
        return True

    bot = data.get("telegram_bot")
    if bot and bot.app:
        try:
            if bot.app.updater and bot.app.updater.running:
                await asyncio.wait_for(bot.app.updater.stop(), timeout=10)
            if bot.app.running:
                await asyncio.wait_for(bot.app.stop(), timeout=10)
            await bot.app.shutdown()
        except asyncio.TimeoutError:
            _LOGGER.warning("NervAI: Telegram app shutdown timed out, forcing.")

    if "db" in data:
        await data["db"].close()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok