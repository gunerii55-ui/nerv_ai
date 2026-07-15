import logging, asyncio
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
        """
        domain: (str) light, climate vb.
        search: (str) opsiyonel arama terimi
        """
        states = self.hass.states.async_all(domain)
        entities = []
        for state in states:
            if not async_should_expose(self.hass, "conversation", state.entity_id):
                continue
            
            name = state.attributes.get("friendly_name", state.entity_id)
            
            # Arama filtresi mantığı
            if search and search.lower() not in name.lower() and search.lower() not in state.entity_id.lower():
                continue
                
            entities.append({"id": state.entity_id, "name": name})
        return entities

    async def execute_service(self, domain, service, entity_id=None, service_data=None):
        data = service_data or {}
        if entity_id: data["entity_id"] = entity_id
        try:
            await self.hass.services.async_call(domain, service, service_data=data, blocking=True)
            return {"status": "ok"}
        except Exception as e:
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
    db = await aiosqlite.connect(hass.config.path("nerv_ai_memory.db"))
    bridge = HABridgeImpl(hass)
    store = MemoryStore(db=db, db_lock=asyncio.Lock())
    await store.async_init_db()
    
    orchestrator = ConversationOrchestrator(store=store, provider=OpenAIProvider(api_key=entry.data.get("openai_api_key")), bridge=bridge)
    bot = TelegramBot(token=entry.data.get("telegram_token"), ha_bridge=bridge, orchestrator=orchestrator)
    hass.data[DOMAIN][entry.entry_id] = {"db": db, "telegram_bot": bot}
    hass.async_create_background_task(bot.initialize_and_start(), name="NervAI_Telegram_Polling")
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    data = hass.data[DOMAIN].get(entry.entry_id)
    if data and "telegram_bot" in data:
        await data["telegram_bot"].app.shutdown()
        await data["db"].close()
    return True