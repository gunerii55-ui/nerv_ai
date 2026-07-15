import logging
import asyncio

_LOGGER = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self, token, ha_bridge, orchestrator):
        self._token = token
        self._orchestrator = orchestrator
        self.app = None

    async def initialize_and_start(self):
        # BURASI KRİTİK: Importlar en tepede değil, fonksiyonun içinde.
        # Bu sayede sistem açılırken diski taramaz.
        from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

        def _build():
            app = ApplicationBuilder().token(self._token).build()
            app.add_handler(CommandHandler("start", self._start))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle))
            return app

        self.app = await asyncio.to_thread(_build)
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()
        _LOGGER.info("NervAI Telegram Bot polling active.")

    async def _start(self, update, context):
        await update.message.reply_text("NervAI Aktif.")

    async def _handle(self, update, context):
        try:
            # Buradaki import da fonksiyon içinde
            from telegram import Update
            reply = await self._orchestrator.handle_message(
                str(update.message.chat_id), 
                update.message.text
            )
            await update.message.reply_text(reply)
        except Exception as e:
            _LOGGER.error(f"Telegram Handle Hatası: {e}")