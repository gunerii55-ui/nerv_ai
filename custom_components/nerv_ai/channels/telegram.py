import logging
import asyncio
from telegram import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

_LOGGER = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self, token, ha_bridge, orchestrator):
        self._token = token
        self._orchestrator = orchestrator
        self.app = None

    async def initialize_and_start(self):
        def _sync_import_and_build():
            from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters
            
            app = ApplicationBuilder().token(self._token).build()
            app.add_handler(CommandHandler("start", self._start))
            app.add_handler(CallbackQueryHandler(self._handle_callback))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle))
            return app

        self.app = await asyncio.to_thread(_sync_import_and_build)
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()
        _LOGGER.info("NervAI Telegram Bot polling started.")

    async def _start(self, update, context):
        await update.message.reply_text("NervAI Aktif.")

    async def _process_orchestrator_reply(self, chat_id, text_input, update_or_query):
        try:
            reply = await self._orchestrator.handle_message(str(chat_id), text_input)
            
            # Yanıt metin mi yoksa butonlu bir dict mi?
            text = reply.get("text") if isinstance(reply, dict) else reply
            buttons_data = reply.get("buttons") if isinstance(reply, dict) else None
            
            reply_markup = None
            if buttons_data:
                keyboard = [[InlineKeyboardButton(btn["text"], callback_data=btn["data"]) for btn in buttons_data]]
                reply_markup = InlineKeyboardMarkup(keyboard)
            
            # GÜVENLİ ARAYÜZ GÜNCELLEMESİ (Callback mi, Mesaj mı?)
            if isinstance(update_or_query, CallbackQuery):
                # Callback ise mevcut mesajı güncelle (edit)
                await update_or_query.edit_message_text(text, reply_markup=reply_markup)
            else:
                # Yeni mesaj ise gönder (reply)
                await update_or_query.message.reply_text(text, reply_markup=reply_markup)
                    
        except Exception as e:
            _LOGGER.error(f"Telegram Handle Hatası: {e}")

    async def _handle(self, update, context):
        await self._process_orchestrator_reply(update.message.chat_id, update.message.text, update)

    async def _handle_callback(self, update, context):
        query = update.callback_query
        # Telegram arayüzündeki yükleniyor spinner'ını hemen durdur
        await query.answer()
        await self._process_orchestrator_reply(query.message.chat_id, query.data, query)