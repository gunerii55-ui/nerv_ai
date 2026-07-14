"""The NervAI integration."""
import logging
import asyncio
import aiosqlite
import uuid

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN

# Gerçek modüllerini çekiyoruz
from .channels.telegram import TelegramBot
from .core.orchestrator import ConversationOrchestrator
from .memory.store import MemoryStore
from .providers.openai import OpenAIProvider  # openai.py olduğunu söyledin

_LOGGER = logging.getLogger(__name__)
PLATFORMS = []

class HABridgeImpl:
    """Implementation of the HomeAssistantBridge."""
    def __init__(self, hass: HomeAssistant):
        self._hass = hass

    async def get_available_entities(self, domain: str) -> list[str]:
        # İleride registry filtresi eklenebilir, şimdilik tüm domain state'leri döner
        states = self._hass.states.async_all(domain)
        return [state.entity_id for state in states]

    async def execute_service(self, domain: str, service: str, entity_id: str, data: dict | None = None) -> dict:
        if entity_id not in self._hass.states.async_entity_ids():
            return {"status": "error", "message": f"Unknown entity: {entity_id}"}
        try:
            # Claude kalkanı: 10 Saniye Timeout
            await asyncio.wait_for(
                self._hass.services.async_call(
                    domain, service, {"entity_id": entity_id, **(data or {})}, blocking=True
                ),
                timeout=10.0
            )
            return {"status": "ok", "message": "Service executed successfully."}
        except asyncio.TimeoutError:
            return {"status": "error", "message": "Service call timed out after 10s"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    async def get_state(self, entity_id: str) -> str | None:
        state = self._hass.states.get(entity_id)
        return state.state if state else None

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up NervAI from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # 1. SQLite Kurulumu
    db_path = hass.config.path("nerv_ai_memory.db")
    db = await aiosqlite.connect(db_path)
    await db.execute("PRAGMA journal_mode=WAL")
    
    # 2. Bridge Enjeksiyonu
    bridge = HABridgeImpl(hass)

    # 3. Config'den API Anahtarlarını Al
    telegram_token = entry.data.get("telegram_token")
    openai_key = entry.data.get("openai_api_key")

    # 4. Gerçek Sınıfların Kurulumu (Memory, Provider, Orchestrator, Bot)
    store = MemoryStore(db=db, db_lock=asyncio.Lock())
    await store.async_init_db()  # Veritabanı tablolarını oluştur
    
    provider = OpenAIProvider(api_key=openai_key)
    
    orchestrator = ConversationOrchestrator(store=store, provider=provider, bridge=bridge)
    bot = TelegramBot(token=telegram_token, ha_bridge=bridge, orchestrator=orchestrator)

    hass.data[DOMAIN][entry.entry_id] = {
        "config": entry.data,
        "db": db,
        "db_lock": asyncio.Lock(),
        "ha_bridge": bridge,
        "telegram_app": bot.app,
    }

    # 5. Botu Arka Planda Başlat
    hass.async_create_background_task(
        bot.initialize_and_start(),
        name="NervAI_Telegram_Polling"
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry strictly and safely."""
    data = hass.data[DOMAIN].get(entry.entry_id)
    if not data:
        return True

    app = data.get("telegram_app")
    if app:
        try:
            if app.updater and app.updater.running:
                await asyncio.wait_for(app.updater.stop(), timeout=10)
            if app.running:
                await asyncio.wait_for(app.stop(), timeout=10)
            await app.shutdown()
        except asyncio.TimeoutError:
            _LOGGER.warning("NervAI: Telegram app shutdown timed out, forcing.")

    if "db" in data:
        await data["db"].close()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
