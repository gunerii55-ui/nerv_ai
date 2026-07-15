import logging, asyncio
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

_LOGGER = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self, token, ha_bridge, orchestrator):
        self._token, self.app = token, None
        self._orchestrator = orchestrator

    async def initialize_and_start(self):
        def _build():
            app = ApplicationBuilder().token(self._token).build()
            app.add_handler(CommandHandler("start", self._start))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle))
            return app
        self.app = await asyncio.to_thread(_build)
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()

    async def _start(self, update, context):
        await update.message.reply_text("NervAI Hazır.")

    async def _handle(self, update, context):
        try:
            reply = await self._orchestrator.handle_message(str(update.message.chat_id), update.message.text)
            await update.message.reply_text(reply)
        except Exception as e:
            await update.message.reply_text(f"Hata: {e}")