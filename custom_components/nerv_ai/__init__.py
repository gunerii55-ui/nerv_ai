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
        self.hass = hass

    async def get_available_entities(self, domain: str, search: str = None) -> list[dict]:
        states = self.hass.states.async_all(domain)
        exposed = [
            {"id": s.entity_id, "name": s.attributes.get("friendly_name", s.entity_id)}
            for s in states if async_should_expose(self.hass, "conversation", s.entity_id)
        ]

        if not search:
            return exposed

        filtered = [
            e for e in exposed
            if search.lower() in e["name"].lower() or search.lower() in e["id"].lower()
        ]

        # Çok dilli (Garage/Garaj) isim uyuşmazlığında modelin 
        # semantik yeteneğine güvenmek için Fallback (Tam Liste)
        return filtered if filtered else exposed

    async def execute_service(self, domain, service, entity_id=None, service_data=None):
        if not entity_id:
            return {"status": "error", "message": "entity_id eksik, önce search_devices ile gerçek entity_id'yi bul."}
        
        if not self.hass.states.get(entity_id):
            return {"status": "error", "message": f"'{entity_id}' isimli bir cihaz sistemde bulunamadı."}

        # LLM Self-Healing Mekanizması
        if not self.hass.services.has_service(domain, service):
            valid_services = list(self.hass.services.async_services().get(domain, {}).keys())
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
                blocking=True
            )
            return {"status": "ok"}
        except Exception as e:
            _LOGGER.error(f"Service Call Error: {e}")
            return {"status": "error", "message": str(e)}

    async def get_state(self, entity_id):
        state = self.hass.states.get(entity_id)
        return {"state": state.state, "attributes": dict(state.attributes)} if state else {"error": "Not found"}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    from .channels.telegram import TelegramBot
    from .core.orchestrator import ConversationOrchestrator
    from .memory.store import MemoryStore
    from .providers.openai import OpenAIProvider
    import aiosqlite

    hass.data.setdefault(DOMAIN, {})
    db = await aiosqlite.connect(hass.config.path(f".storage/nerv_ai_{entry.entry_id}.db"))
    bridge = HABridgeImpl(hass)
    store = MemoryStore(db=db, db_lock=asyncio.Lock())
    await store.async_init_db()

    orchestrator = ConversationOrchestrator(
        store=store,
        provider=OpenAIProvider(api_key=entry.data.get("openai_api_key")),
        bridge=bridge,
    )
    bot = TelegramBot(token=entry.data.get("telegram_token"), ha_bridge=bridge, orchestrator=orchestrator)
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
            _LOGGER.warning("NervAI: Telegram app shutdown timed out")

    if "db" in data:
        await data["db"].close()

    hass.data[DOMAIN].pop(entry.entry_id)
    return True