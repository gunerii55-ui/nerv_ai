import logging
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN

_LOGGER = logging.getLogger(__name__)

class ProactiveManager:
    def __init__(self, hass, telegram_bot, store):
        self.hass = hass
        self.telegram_bot = telegram_bot
        self.store = store
        self._unsub_battery = None
        self._notified = set()

    async def setup_battery_monitoring(self):
        # Sadece 'device_class: battery' olan sensörleri dinle
        battery_entities = [
            state.entity_id for state in self.hass.states.async_all()
            if state.attributes.get("device_class") == "battery"
        ]

        if not battery_entities:
            _LOGGER.debug("Batarya sensörü bulunamadı.")
            return

        self._unsub_battery = async_track_state_change_event(
            self.hass, battery_entities, self._on_battery_change
        )
        _LOGGER.info(f"{len(battery_entities)} batarya sensörü takibe alındı.")

    async def _on_battery_change(self, event):
        new_state = event.data.get("new_state")
        if not new_state or new_state.state in [STATE_UNAVAILABLE, STATE_UNKNOWN]:
            return

        try:
            value = float(new_state.state)
            entity_id = new_state.entity_id
            
            # Eşik değeri: %20
            if value < 20 and entity_id not in self._notified:
                chat_id = await self.store.get_config("authorized_chat_id")
                
                # Bot uygulaması hazır mı ve chat_id kayıtlı mı?
                if chat_id and self.telegram_bot and self.telegram_bot.app:
                    await self.telegram_bot.app.bot.send_message(
                        chat_id=chat_id,
                        text=f"⚠️ {new_state.name} pil seviyesi kritik: %{value}"
                    )
                    self._notified.add(entity_id)
            
            # Eşik üstüne çıkarsa cooldown'u sıfırla
            elif value >= 20:
                self._notified.discard(entity_id)
                
        except (ValueError, TypeError):
            pass

    def unload(self):
        # Event listener'ı temizle (Memory leak önleme)
        if self._unsub_battery:
            self._unsub_battery()
            self._unsub_battery = None
            _LOGGER.info("ProactiveManager batarya takibi durduruldu.")