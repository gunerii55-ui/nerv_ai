import logging
from datetime import timedelta
from homeassistant.helpers.event import async_track_state_change_event, async_call_later, async_track_time_interval
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, STATE_ON, STATE_OFF, STATE_OPEN, STATE_CLOSED
from homeassistant.util import dt as dt_util
from homeassistant.helpers import entity_registry as er

_LOGGER = logging.getLogger(__name__)

class ProactiveManager:
    def __init__(self, hass, telegram_bot, store):
        self.hass = hass
        self.telegram_bot = telegram_bot
        self.store = store
        self._unsub_battery = None
        self._unsub_duration = None
        self._unsub_cleanup = None
        self._unsub_registry = None
        self._timers = {}

    async def setup_monitoring(self):
        # 1. Pil Seviyesi İzleme
        battery_entities = [
            s.entity_id for s in self.hass.states.async_all()
            if s.attributes.get("device_class") == "battery"
        ]
        if battery_entities:
            self._unsub_battery = async_track_state_change_event(
                self.hass, battery_entities, self._on_battery_change
            )

        # 2. Açık Kalma Süresi İzleme (Kapı/Klima)
        duration_entities = [
            s.entity_id for s in self.hass.states.async_all()
            if s.domain in ["climate", "cover"] or (s.domain == "binary_sensor" and s.attributes.get("device_class") in ["door", "window"])
        ]
        if duration_entities:
            self._unsub_duration = async_track_state_change_event(
                self.hass, duration_entities, self._on_duration_change
            )
            await self._reconcile_on_startup(duration_entities)

        # 3. Periyodik Log Temizliği
        self._unsub_cleanup = async_track_time_interval(
            self.hass, self._run_periodic_cleanup, timedelta(days=7)
        )

        # 4. Yeni Cihaz Keşfi (Entity Registry İzleme)
        self._unsub_registry = self.hass.bus.async_listen(
            "entity_registry_updated", self._on_entity_registry_updated
        )

    async def _on_entity_registry_updated(self, event):
        # Yalnızca yeni oluşturulan cihazları (create action) filtrele
        if event.data.get("action") != "create":
            return
            
        entity_id = event.data.get("entity_id")
        if not entity_id:
            return
            
        domain = entity_id.split(".")[0]
        VALID_DOMAINS = ["light", "switch", "cover", "lock", "climate", "fan", "alarm_control_panel", "media_player", "vacuum", "sensor", "binary_sensor", "camera"]
        if domain not in VALID_DOMAINS:
            return

        registry = er.async_get(self.hass)
        entry = registry.async_get(entity_id)
        if not entry:
            return
            
        friendly_name = entry.name or entry.original_name or entity_id.split(".")[1].replace("_", " ")
        
        chat_id = await self.store.get_config("authorized_chat_id")
        if chat_id and self.telegram_bot and hasattr(self.telegram_bot, '_orchestrator'):
            # Orchestrator üzerinden pending state ve hash id oluştur
            action_id = self.telegram_bot._orchestrator.create_pending_alias(chat_id, entity_id, friendly_name)
            
            message = f"🔌 **Yeni Cihaz Bulundu:** `{entity_id}`\n\nSistem bu cihazı asistan için otomatik olarak kaydetti. Doğal dilde komut verebilmek için bir takma ad atamak ister misiniz?\n\nÖnerilen isim: *{friendly_name}*"
            buttons = [
                {"text": "✅ Onayla", "data": f"approve_alias:{action_id}"},
                {"text": "✍️ Özel İsim", "data": f"custom_alias:{action_id}"},
                {"text": "❌ Yoksay", "data": f"cancel_alias:{action_id}"}
            ]
            
            await self._send_telegram_alert(message, buttons=buttons)

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
                    if not await self.store.is_notified(entity_id):
                        await self._send_telegram_alert(
                            f"⚠️ Uyarı: '{state.name}' adlı {action_name} uzun süredir açık (yeniden başlatma sonrası tespit edildi)!"
                        )
                        await self.store.mark_notified(entity_id)
                else:
                    self._timers[entity_id] = async_call_later(
                        self.hass, remaining, self._create_timer_callback(entity_id, state.name, action_name)
                    )

    def _create_timer_callback(self, entity_id, name, action_name):
        async def _timer_finished(now):
            self._timers.pop(entity_id, None)
            if not await self.store.is_notified(entity_id):
                await self._send_telegram_alert(f"⚠️ Uyarı: '{name}' adlı {action_name} uzun süredir açık unutulmuş olabilir!")
                await self.store.mark_notified(entity_id)
        return _timer_finished

    async def _on_battery_change(self, event):
        new_state = event.data.get("new_state")
        if not new_state or new_state.state in [STATE_UNAVAILABLE, STATE_UNKNOWN]:
            return

        try:
            value = float(new_state.state)
            entity_id = new_state.entity_id
            
            if value < 20 and not await self.store.is_notified(entity_id):
                await self._send_telegram_alert(f"⚠️ {new_state.name} pil seviyesi kritik: %{value}")
                await self.store.mark_notified(entity_id)
            elif value >= 20:
                await self.store.clear_notified(entity_id)
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
                
            await self.store.clear_notified(entity_id)

    async def _run_periodic_cleanup(self, now):
        _LOGGER.info("Periyodik action_log temizliği başlatılıyor.")
        await self.store.cleanup_action_logs()

    async def _send_telegram_alert(self, message, buttons=None):
        chat_id = await self.store.get_config("authorized_chat_id")
        if chat_id and self.telegram_bot and self.telegram_bot.app:
            try:
                reply_markup = None
                if buttons:
                    from telegram import InlineKeyboardMarkup, InlineKeyboardButton
                    keyboard = [[InlineKeyboardButton(btn["text"], callback_data=btn["data"]) for btn in buttons]]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                await self.telegram_bot.app.bot.send_message(
                    chat_id=chat_id, 
                    text=message, 
                    reply_markup=reply_markup, 
                    parse_mode="Markdown"
                )
            except Exception as e:
                _LOGGER.error(f"Proaktif bildirim gönderilemedi: {e}")

    def unload(self):
        if self._unsub_battery:
            self._unsub_battery()
        if self._unsub_duration:
            self._unsub_duration()
        if self._unsub_cleanup:
            self._unsub_cleanup()
        if self._unsub_registry:
            self._unsub_registry()
            
        for cancel_timer in self._timers.values():
            cancel_timer()
        self._timers.clear()
        
        _LOGGER.info("ProactiveManager güvenli bir şekilde kapatıldı.")