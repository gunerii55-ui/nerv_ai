"""Telegram channel implementation for NervAI."""
import logging
from .base import HomeAssistantBridge

_LOGGER = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self, token: str, ha_bridge: HomeAssistantBridge):
        self._token = token
        self._ha_bridge = ha_bridge
        self.app = ApplicationBuilder().token(self._token).build()
        
        # Handler'ları kayıt et
        self.app.add_handler(CommandHandler("start", self._start_command))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))

    async def initialize_and_start(self):
        from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
        """HA async_setup_entry içinde çağrılacak asenkron başlatıcı."""
        await self.app.initialize()
        await self.app.start()
        # Kritik Düzeltme: Bekleyen eski güncellemeleri çöpe at
        await self.app.updater.start_polling(drop_pending_updates=True)
        _LOGGER.info("NervAI Telegram Bot started polling.")

    async def _start_command(self, update, context):
        await update.message.reply_text("NervAI is online and connected to Home Assistant.")

    # Sınıfın __init__ metoduna orchestrator eklendiğini varsayıyoruz:
    # def __init__(self, token: str, ha_bridge: HomeAssistantBridge, orchestrator):
    #    self._orchestrator = orchestrator

    async def _handle_message(self, update, context):
        chat_id = str(update.message.chat_id)
        user_text = update.message.text
        
        # Sadece Orchestrator'ı çağır
        reply = await self._orchestrator.handle_message(chat_id, user_text)
        await update.message.reply_text(reply)