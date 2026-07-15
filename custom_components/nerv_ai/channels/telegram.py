import logging
import asyncio

_LOGGER = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self, token, ha_bridge, orchestrator):
        self._token = token
        self._bridge = ha_bridge
        self._orchestrator = orchestrator
        self.app = None

    def _sync_build_app(self):
        """Ağır kütüphane yüklemelerini ve SSL sertifika okumalarını Thread içinde yapar."""
        from telegram.ext import ApplicationBuilder
        return ApplicationBuilder().token(self._token).build()

    async def initialize_and_start(self):
        # 1. Uygulamayı arka plan iş parçacığında (Thread) kur. Event Loop bloklanmaz!
        self.app = await asyncio.to_thread(self._sync_build_app)

        # 2. Modülleri burada yerel olarak çağır.
        from telegram.ext import CommandHandler, MessageHandler, filters
        
        # 3. Handler'ları ekle
        self.app.add_handler(CommandHandler("start", self._start_command))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))

        # 4. Botu Başlat
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()
        _LOGGER.warning("NervAI Telegram Bot started polling.")

    async def _start_command(self, update, context):
        await update.message.reply_text("NervAI Sistemine Hoş Geldiniz! Nasıl yardımcı olabilirim?")

    async def _handle_message(self, update, context):
        chat_id = str(update.message.chat_id)
        user_message = update.message.text
        
        # LLM Orchestrator'a mesajı yolla ve yanıtı al
        reply = await self._orchestrator.handle_message(chat_id, user_message)
        await update.message.reply_text(reply)