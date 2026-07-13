"""Telegram channel implementation for NervAI."""
import logging
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from .base import HomeAssistantBridge

_LOGGER = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self, token: str, ha_bridge: HomeAssistantBridge, orchestrator):
        self._token = token
        self._ha_bridge = ha_bridge
        self._orchestrator = orchestrator
        self.app = ApplicationBuilder().token(self._token).build()
        
        # Handler'ları kayıt et
        self.app.add_handler(CommandHandler("start", self._start_command))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))

    async def initialize_and_start(self):
        """HA async_setup_entry içinde çağrılacak asenkron başlatıcı."""
        await self.app.initialize()
        await self.app.start()
        # Kritik Düzeltme: Bekleyen eski güncellemeleri çöpe at
        await self.app.updater.start_polling(drop_pending_updates=True)
        _LOGGER.warning("NervAI Telegram Bot started polling.")

    async def _start_command(self, update, context):
        _LOGGER.warning("TEST: /start komutu tetiklendi!")
        await update.message.reply_text("NervAI is online and connected to Home Assistant.")

    async def _handle_message(self, update, context):
        _LOGGER.warning("TEST: Normal mesaj alindi: %s", update.message.text)
        chat_id = str(update.message.chat_id)
        user_text = update.message.text
        
        try:
            # Orchestrator'ı çağır
            reply = await self._orchestrator.handle_message(chat_id, user_text)
            await update.message.reply_text(reply)
        except Exception as e:
            _LOGGER.error("CRITICAL: Orchestrator hatası: %s", e, exc_info=True)
            await update.message.reply_text("Arka planda bir hata oluştu, logları kontrol et.")