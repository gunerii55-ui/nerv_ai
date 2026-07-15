import logging
import asyncio

_LOGGER = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self, token, ha_bridge, orchestrator):
        self._token = token
        self._orchestrator = orchestrator
        self.app = None

    async def initialize_and_start(self):
        # Bu yardımcı fonksiyon, HER ŞEYİ (import + build) thread içinde yapar.
        # Böylece ana loop'un haberi bile olmaz.
        def _sync_import_and_build():
            # Importlar burada, thread'in içinde!
            from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
            
            # Uygulamayı inşa et
            app = ApplicationBuilder().token(self._token).build()
            
            # Handler'ları ekle
            app.add_handler(CommandHandler("start", self._start))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle))
            
            return app

        # Şimdi thread'e gönderiyoruz.
        self.app = await asyncio.to_thread(_sync_import_and_build)
        
        # Async işlemleri ana loop'ta devam ettir (bunlar bloklamaz)
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()
        _LOGGER.info("NervAI Telegram Bot polling started.")

    async def _start(self, update, context):
        await update.message.reply_text("NervAI Aktif.")

    async def _handle(self, update, context):
        try:
            # Buradaki reply işlemini bekliyoruz
            reply = await self._orchestrator.handle_message(
                str(update.message.chat_id), 
                update.message.text
            )
            await update.message.reply_text(reply)
        except Exception as e:
            _LOGGER.error(f"Telegram Handle Hatası: {e}")