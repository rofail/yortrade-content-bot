"""
Content Automation Bot - Main Entry Point
Telegram bot untuk generate konten sosmed automatically
"""

import logging
import os
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)
from config import TELEGRAM_BOT_TOKEN, CALLBACK_DATA_SEP
from handlers.generate import start_buat, niche_selected, topic_input, show_niche_selection
from handlers.review import approve_content, revise_content, revision_input, regenerate_content

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
WAITING_TOPIC = 1
WAITING_REVISION = 2

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    user = update.effective_user
    welcome_text = f"""
👋 **Halo {user.first_name}!**

Selamat datang di **Content Automation Bot**!

/buat — Generate konten baru
/help — Lihat semua commands
"""
    await update.message.reply_text(welcome_text)

def main():
    """Start the bot."""
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    logger.info("🚀 Bot started!")
    application.run_polling()

if __name__ == "__main__":
    main()
