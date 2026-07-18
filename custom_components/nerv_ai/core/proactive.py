import logging
from datetime import timedelta
from homeassistant.helpers.event import async_track_state_change_event, async_call_later, async_track_time_interval
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, STATE_ON, STATE_OFF, STATE_OPEN, STATE_CLOSED
from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)

class ProactiveManager:
    def __init__(self, hass, telegram_bot, store):
        self.hass = hass
        self.telegram_bot = telegram_bot
        self.store = store
        self._unsub_battery = None
        self._unsub_duration = None
        self._unsub_cleanup = None
        self._notified_battery = set()
        self._timers = {}

    async def setup_monitoring(self):
        battery_entities = [
            s.entity_id for s in self.hass.states.async_all()
            if s.attributes.get("device_class") == "battery"
        ]
        if battery_entities:
            self._unsub_battery = async_track_state_change_event(
                self.hass, battery_entities, self._on_battery_change
            )

        duration_entities = [
            s.entity_id for s in self.hass.states.async_all()
            if s.domain in ["climate", "cover"] or (s.domain == "binary_sensor" and s.attributes.get("device_class") in ["door", "window"])
        ]
        if duration_entities:
            self._unsub_duration = async_track_state_change_event(
                self.hass, duration_entities, self._on_duration_change
            )
            # D-2 Restart Uzlaştırması
            await self._reconcile_on_startup(duration_entities)

        # E-2 Periyodik Temizlik (7 günde bir rolling window taraması yapar)
        self._unsub_cleanup = async_track_time_interval(
            self.hass, self._run_periodic_cleanup, timedelta(days=7)
        )

    async def _reconcile_on_startup(self, tracked_entities):
        now = dt_util.utcnow()
        for entity_id in tracked_entities:
            state = self.hass.states.get(entity_id)
            if not state or state.state in [STATE_UNAVAILABLE, STATE_UNKNOWN]:
                continue
            
            domain = entity_id.split(".")[0]
            state_val = state.state

            if (domain == "climate" and state_val != STATE_OFF) or \
               (domain in ["cover", "binary_sensor"] and state_val == STATE_OPEN):
                
                delay = 21600 if domain == "climate" else 900
                action_name = "klima" if domain == "climate" else "kapı/pencere"
                
                elapsed = (now - state.last_changed).total_seconds()
                remaining = delay - elapsed

                if remaining <= 0:
                    await self._send_telegram_alert(
                        f"⚠️ Uyarı: '{state.name}' adlı {action_name} uzun süredir açık (yeniden başlatma sonrası tespit edildi)!"
                    )
                else:
                    self._timers[entity_id] = async_call_later(
                        self.hass, remaining, self._create_timer_callback(entity_id, state.name, action_name)
                    )

    def _create_timer_callback(self, entity_id, name, action_name):
        async def _timer_finished(now):
            self._timers.pop(entity_id, None)
            await self._send_telegram_alert(f"⚠️ Uyarı: '{name}' adlı {action_name} uzun süredir açık unutulmuş olabilir!")
        return _timer_finished

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

        if (domain == "climate" and state_val != STATE_OFF) or \
           (domain in ["cover", "binary_sensor"] and state_val == STATE_OPEN):
            
            if entity_id not in self._timers:
                delay = 21600 if domain == "climate" else 900
                action_name = "klima" if domain == "climate" else "kapı/pencere"
                self._timers[entity_id] = async_call_later(
                    self.hass, delay, self._create_timer_callback(entity_id, new_state.name, action_name)
                )

        elif (domain == "climate" and state_val == STATE_OFF) or \
             (domain in ["cover", "binary_sensor"] and state_val == STATE_CLOSED):
            
            cancel_timer = self._timers.pop(entity_id, None)
            if cancel_timer:
                cancel_timer()

    async def _run_periodic_cleanup(self, now):
        _LOGGER.info("Periyodik action_log temizliği başlatılıyor.")
        await self.store.cleanup_action_logs()

    async def _send_telegram_alert(self, message):
        chat_id = await self.store.get_config("authorized_chat_id")
        if chat_id and self.telegram_bot and self.telegram_bot.app:
            try:
                await self.telegram_bot.app.bot.send_message(chat_id=chat_id, text=message)
            except Exception as e:
                _LOGGER.error(f"Proaktif bildirim gönderilemedi: {e}")

    def unload(self):
        if self._unsub_battery:
            self._unsub_battery()
        if self._unsub_duration:
            self._unsub_duration()
        if self._unsub_cleanup:
            self._unsub_cleanup()
            
        for cancel_timer in self._timers.values():
            cancel_timer()
        self._timers.clear()
        
        _LOGGER.info("ProactiveManager güvenli bir şekilde kapatıldı.")