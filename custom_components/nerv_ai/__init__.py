"""The NervAI integration."""
import logging
import asyncio
import aiosqlite

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
PLATFORMS = []

class HABridgeImpl:
    """Implementation of the HomeAssistantBridge."""
    def __init__(self, hass: HomeAssistant):
        self._hass = hass
        self._pending_actions = {}

    async def execute_tool_call(self, call: dict, chat_id: str) -> dict:
        args = call.get("arguments", {})
        domain = args.get("domain")
        service = args.get("service")
        
        if domain in {"lock", "alarm_control_panel", "cover"}:
            token = str(uuid.uuid4())[:8]
            self._pending_actions[token] = call
            return {
                "status": "confirmation_required", 
                "token": token,
                "message": f"{domain}.{service} requires confirmation. Command: /confirm {token}"
            }
        
        return await self._call_service_safe(domain, service, args.get("entity_id"), args.get("data"))

    async def _call_service_safe(self, domain: str, service: str, entity_id: str, data: dict | None = None) -> dict:
        if entity_id not in self._hass.states.async_entity_ids():
            return {"status": "error", "message": f"Unknown entity: {entity_id}"}
        try:
            await self._hass.services.async_call(
                domain, service, {"entity_id": entity_id, **(data or {})},
                blocking=True # İşlem bitmeden cevap dönme
            )
            return {"status": "ok", "message": "Service executed successfully."}
        except Exception as e:
            # vol.Invalid, ServiceNotFound vb. hepsini yut ve döndür. 
            # Hata patlarsa task çöker.
            return {"status": "error", "message": str(e)}

    async def get_state(self, entity_id: str) -> str | None:
        state = self._hass.states.get(entity_id)
        return state.state if state else None

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up NervAI from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # 1. SQLite Kurulumu (WAL Mode & Lock)
    db_path = hass.config.path("nerv_ai_memory.db")
    db = await aiosqlite.connect(db_path)
    await db.execute("PRAGMA journal_mode=WAL")
    
    # 2. Bridge Enjeksiyonu
    bridge = HABridgeImpl(hass)

    hass.data[DOMAIN][entry.entry_id] = {
        "config": entry.data,
        "db": db,
        "db_lock": asyncio.Lock(),
        "ha_bridge": bridge,
        # telegram_app = TODO: channels/telegram.py eklendikten sonra buraya tanımlanacak.
    }

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