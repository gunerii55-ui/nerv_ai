import logging
from homeassistant.helpers.event import async_track_state_change_event, async_call_later
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, STATE_ON, STATE_OFF, STATE_OPEN, STATE_CLOSED

_LOGGER = logging.getLogger(__name__)

class ProactiveManager:
    def __init__(self, hass, telegram_bot, store):
        self.hass = hass
        self.telegram_bot = telegram_bot
        self.store = store
        self._unsub_battery = None
        self._unsub_duration = None
        self._notified_battery = set()
        
        # Timer referanslarını tutacağımız sözlük: { "entity_id": cancel_callable() }
        self._timers = {}

    async def setup_monitoring(self):
        # 1. Batarya Takibi (D-1)
        battery_entities = [
            s.entity_id for s in self.hass.states.async_all()
            if s.attributes.get("device_class") == "battery"
        ]
        if battery_entities:
            self._unsub_battery = async_track_state_change_event(
                self.hass, battery_entities, self._on_battery_change
            )

        # 2. Süreli Açık Kalma Takibi (D-2) - Climate ve Cover
        duration_entities = [
            s.entity_id for s in self.hass.states.async_all()
            if s.domain in ["climate", "cover"] or (s.domain == "binary_sensor" and s.attributes.get("device_class") in ["door", "window"])
        ]
        if duration_entities:
            self._unsub_duration = async_track_state_change_event(
                self.hass, duration_entities, self._on_duration_change
            )

    async def _on_battery_change(self, event):
        new_state = event.data.get("new_state")
        if not new_state or new_state.state in [STATE_UNAVAILABLE, STATE_UNKNOWN]:
            return

        try:
            value = float(new_state.state)
            entity_id = new_state.entity_id
            
            if value < 20 and entity_id not in self._notified_battery:
                await self._send_telegram_alert(f"⚠️ {new_state.name} pil seviyesi kritik: %{value}")
                self._notified_battery.add(entity_id)
            elif value >= 20:
                self._notified_battery.discard(entity_id)
        except (ValueError, TypeError):
            pass

    async def _on_duration_change(self, event):
        entity_id = event.data.get("entity_id")
        new_state = event.data.get("new_state")
        
        if not new_state or new_state.state in [STATE_UNAVAILABLE, STATE_UNKNOWN]:
            return

        domain = entity_id.split(".")[0]
        state_val = new_state.state

        # Klima açıldıysa veya Kapı/Pencere açıldıysa
        if (domain == "climate" and state_val != STATE_OFF) or \
           (domain in ["cover", "binary_sensor"] and state_val == STATE_OPEN):
            
            # Zaten bir timer varsa dokunma
            if entity_id not in self._timers:
                # Örnek: Klima için 6 saat (21600 sn), Kapı için 15 dakika (900 sn)
                delay = 21600 if domain == "climate" else 900
                action_name = "klima" if domain == "climate" else "kapı/pencere"
                
                # Callback fonksiyonu (Süre dolduğunda çalışacak)
                async def _timer_finished(now):
                    self._timers.pop(entity_id, None) # Timer bitti, referansı sil
                    await self._send_telegram_alert(
                        f"⚠️ Uyarı: '{new_state.name}' adlı {action_name} uzun süredir açık unutulmuş olabilir!"
                    )

                # Timer'ı başlat ve iptal referansını sakla
                self._timers[entity_id] = async_call_later(self.hass, delay, _timer_finished)

        # Klima kapandıysa veya Kapı/Pencere kapandıysa
        elif (domain == "climate" and state_val == STATE_OFF) or \
             (domain in ["cover", "binary_sensor"] and state_val == STATE_CLOSED):
            
            # Aktif timer varsa İPTAL ET
            cancel_timer = self._timers.pop(entity_id, None)
            if cancel_timer:
                cancel_timer() # HA API: Çağrılabilir nesneyi çalıştırmak timer'ı iptal eder

    async def _send_telegram_alert(self, message):
        chat_id = await self.store.get_config("authorized_chat_id")
        if chat_id and self.telegram_bot and self.telegram_bot.app:
            try:
                await self.telegram_bot.app.bot.send_message(chat_id=chat_id, text=message)
            except Exception as e:
                _LOGGER.error(f"Proaktif bildirim gönderilemedi: {e}")

    def unload(self):
        # 1. Event listener'ları temizle
        if self._unsub_battery:
            self._unsub_battery()
        if self._unsub_duration:
            self._unsub_duration()
            
        # 2. Bekleyen tüm timer'ları güvenlice iptal et (Memory Leak Koruması)
        for cancel_timer in self._timers.values():
            cancel_timer()
        self._timers.clear()
        
        _LOGGER.info("ProactiveManager güvenli bir şekilde kapatıldı ve timer'lar temizlendi.")