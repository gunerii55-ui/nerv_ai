import logging
import asyncio

_LOGGER = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self, token, ha_bridge, orchestrator):
        self._token = token
        self._bridge = ha_bridge
        self._orchestrator = orchestrator
        self.app = None

    async def initialize_and_start(self):
        def _build_app_sync():
            # Import ve I/O işlemleri thread içinde izole
            from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
            app = ApplicationBuilder().token(self._token).build()
            app.add_handler(CommandHandler("start", self._start_command))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))
            return app

        self.app = await asyncio.to_thread(_build_app_sync)
        
        # Async işlemleri devam ettir
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()
        _LOGGER.info("NervAI Telegram Bot active.")

    async def _start_command(self, update, context):
        await update.message.reply_text("NervAI aktif.")

    async def _handle_message(self, update, context):
        reply = await self._orchestrator.handle_message(str(update.message.chat_id), update.message.text)
        await update.message.reply_text(reply)