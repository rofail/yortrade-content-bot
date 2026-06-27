"""
YorTrade Content Automation Bot - Self-Contained
Semua handler dan logic dalam satu file untuk deployment yang simpel
"""

import logging
import os
import anthropic
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Config dari environment variables
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')

# Conversation states
WAITING_TOPIC = 1
WAITING_REVISION = 2

# Definisi niche
NICHES = {
    'trading': '📈 Trading',
    'affiliate': '💰 Affiliate Marketing',
    'tech': '🤖 Tech/AI',
    'motivation': '💪 Motivasi/Mindset',
    'health': '🏥 Health & Fitness'
}

# Prompt per niche
PROMPTS = {
    'trading': """Kamu adalah content creator trading profesional. Buat konten edukatif tentang: {topic}

Format output:
JUDUL: [Judul menarik, max 10 kata]
CAPTION: [Caption 150-200 kata, engaging, pakai emoji, ada call-to-action]
HASHTAGS: [10-15 hashtag relevan]

Gunakan bahasa Indonesia yang santai tapi profesional.""",

    'affiliate': """Kamu adalah content creator affiliate marketing. Buat konten marketing tentang: {topic}

Format output:
JUDUL: [Judul menarik, max 10 kata]
CAPTION: [Caption 150-200 kata, persuasif, pakai emoji, highlight benefit]
HASHTAGS: [10-15 hashtag relevan]

Gunakan bahasa Indonesia yang engaging dan persuasif.""",

    'tech': """Kamu adalah content creator tech & AI. Buat konten edukasi tentang: {topic}

Format output:
JUDUL: [Judul menarik, max 10 kata]
CAPTION: [Caption 150-200 kata, informatif, pakai emoji, mudah dipahami]
HASHTAGS: [10-15 hashtag relevan]

Gunakan bahasa Indonesia yang modern dan tech-savvy.""",

    'motivation': """Kamu adalah motivational content creator. Buat konten motivasi tentang: {topic}

Format output:
JUDUL: [Judul menarik, max 10 kata]
CAPTION: [Caption 150-200 kata, inspiratif, pakai emoji, emosional]
HASHTAGS: [10-15 hashtag relevan]

Gunakan bahasa Indonesia yang memotivasi dan inspiring.""",

    'health': """Kamu adalah health & fitness content creator. Buat konten kesehatan tentang: {topic}

Format output:
JUDUL: [Judul menarik, max 10 kata]
CAPTION: [Caption 150-200 kata, informatif, pakai emoji, ada tips praktis]
HASHTAGS: [10-15 hashtag relevan]

Gunakan bahasa Indonesia yang informatif dan menyehatkan."""
}


async def generate_with_claude(niche, topic):
    """Generate konten menggunakan Anthropic Claude."""
    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    prompt = PROMPTS.get(niche, PROMPTS['tech']).format(topic=topic)
    message = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text


async def start(update, context):
    """Handle /start command."""
    user = update.effective_user
    await update.message.reply_text(
        f"👋 *Halo {user.first_name}!*\n\n"
        "Selamat datang di *YorTrade Content Bot* 🚀\n\n"
        "Aku bisa bantu generate konten otomatis untuk sosmed kamu!\n\n"
        "📝 *Commands:*\n"
        "/buat \u2014 Generate konten baru\n"
        "/help \u2014 Lihat semua commands",
        parse_mode='Markdown'
    )


async def help_command(update, context):
    """Handle /help command."""
    await update.message.reply_text(
        "🤖 *YorTrade Content Bot*\n\n"
        "📝 *Commands:*\n"
        "/start \u2014 Mulai bot\n"
        "/buat \u2014 Generate konten baru\n"
        "/cancel \u2014 Batalkan proses\n"
        "/help \u2014 Tampilkan bantuan ini\n\n"
        "🎯 *Cara Pakai:*\n"
        "1. Ketik /buat\n"
        "2. Pilih niche konten\n"
        "3. Masukkan topik\n"
        "4. Review & approve konten!",
        parse_mode='Markdown'
    )


async def start_buat(update, context):
    """Mulai generate konten - tampilkan pilihan niche."""
    keyboard = [
        [InlineKeyboardButton(name, callback_data=f"niche:{key}")]
        for key, name in NICHES.items()
    ]
    await update.message.reply_text(
        "🎯 *Pilih Niche Konten:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return WAITING_TOPIC


async def niche_selected(update, context):
    """Handle pilihan niche."""
    query = update.callback_query
    await query.answer()
    niche_key = query.data.replace("niche:", "")
    niche_name = NICHES.get(niche_key, niche_key)
    context.user_data['niche'] = niche_key
    context.user_data['niche_name'] = niche_name
    await query.edit_message_text(
        f"✅ Niche: *{niche_name}*\n\n📝 Ketik topik yang mau kamu buat kontennya:",
        parse_mode='Markdown'
    )
    return WAITING_TOPIC


async def topic_input(update, context):
    """Handle input topik dan generate konten."""
    topic = update.message.text
    niche = context.user_data.get('niche', 'tech')
    niche_name = context.user_data.get('niche_name', 'Tech/AI')
    context.user_data['topic'] = topic

    loading_msg = await update.message.reply_text(
        f"⏳ Generating konten *{niche_name}*: {topic}\n\nMohon tunggu 15 detik...",
        parse_mode='Markdown'
    )

    try:
        content = await generate_with_claude(niche, topic)
        context.user_data['generated_content'] = content
        await loading_msg.delete()

        keyboard = [[
            InlineKeyboardButton("✅ Approve", callback_data="action:approve"),
            InlineKeyboardButton("✏️ Revisi", callback_data="action:revise"),
            InlineKeyboardButton("🔄 Ulang", callback_data="action:regenerate")
        ]]

        preview = f"📋 *Preview Konten:*\n\n{content}"
        if len(preview) > 4000:
            preview = preview[:3997] + "..."

        await update.message.reply_text(
            preview,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error generating content: {e}")
        await loading_msg.edit_text(f"❌ Error: {str(e)}\n\nCoba lagi dengan /buat")

    return WAITING_REVISION


async def handle_action(update, context):
    """Handle tombol aksi konten."""
    query = update.callback_query
    await query.answer()
    action = query.data.replace("action:", "")

    if action == "approve":
        await query.edit_message_text(
            "✅ *Konten Approved!* 🎉\n\nKonten siap untuk diposting!\n\nMau generate lagi? Ketik /buat",
            parse_mode='Markdown'
        )
        context.user_data.clear()
        return ConversationHandler.END

    elif action == "revise":
        await query.edit_message_text(
            "✏️ *Mode Revisi*\n\nKetik instruksi revisi kamu:",
            parse_mode='Markdown'
        )
        return WAITING_REVISION

    elif action == "regenerate":
        niche = context.user_data.get('niche', 'tech')
        niche_name = context.user_data.get('niche_name', 'Tech/AI')
        topic = context.user_data.get('topic', '')

        await query.edit_message_text(
            f"⏳ Regenerating konten *{niche_name}*...",
            parse_mode='Markdown'
        )

        try:
            content = await generate_with_claude(niche, topic)
            context.user_data['generated_content'] = content

            keyboard = [[
                InlineKeyboardButton("✅ Approve", callback_data="action:approve"),
                InlineKeyboardButton("✏️ Revisi", callback_data="action:revise"),
                InlineKeyboardButton("🔄 Ulang", callback_data="action:regenerate")
            ]]

            preview = f"📋 *Preview Konten (Baru):*\n\n{content}"
            if len(preview) > 4000:
                preview = preview[:3997] + "..."

            await query.edit_message_text(
                preview,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
        except Exception as e:
            await query.edit_message_text(f"❌ Error: {str(e)}\n\nKetik /buat untuk coba lagi")
            return ConversationHandler.END

    return WAITING_REVISION


async def revision_input(update, context):
    """Handle input revisi konten."""
    revision_text = update.message.text
    original_content = context.user_data.get('generated_content', '')

    loading_msg = await update.message.reply_text("⏳ Merevisi konten...")

    try:
        client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
        revision_prompt = f"""Revisi konten berikut sesuai instruksi:

KONTEN ORIGINAL:
{original_content}

INSTRUKSI REVISI: {revision_text}

Berikan konten yang sudah direvisi dalam format yang sama (JUDUL, CAPTION, HASHTAGS)."""

        message = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": revision_prompt}]
        )

        revised = message.content[0].text
        context.user_data['generated_content'] = revised
        await loading_msg.delete()

        keyboard = [[
            InlineKeyboardButton("✅ Approve", callback_data="action:approve"),
            InlineKeyboardButton("✏️ Revisi Lagi", callback_data="action:revise"),
            InlineKeyboardButton("🔄 Ulang", callback_data="action:regenerate")
        ]]

        preview = f"📋 *Preview Konten (Revisi):*\n\n{revised}"
        if len(preview) > 4000:
            preview = preview[:3997] + "..."

        await update.message.reply_text(
            preview,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    except Exception as e:
        await loading_msg.edit_text(f"❌ Error: {str(e)}\n\nKetik /buat untuk coba lagi")

    return WAITING_REVISION


async def cancel(update, context):
    """Cancel conversation."""
    await update.message.reply_text("❌ Dibatalkan. Ketik /buat untuk mulai lagi.")
    context.user_data.clear()
    return ConversationHandler.END


def main():
    """Jalankan bot."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN tidak di-set!")
        return
    if not ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY tidak di-set!")
        return

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("buat", start_buat)],
        states={
            WAITING_TOPIC: [
                CallbackQueryHandler(niche_selected, pattern="^niche:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, topic_input)
            ],
            WAITING_REVISION: [
                CallbackQueryHandler(handle_action, pattern="^action:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, revision_input)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(conv_handler)

    logger.info("YorTrade Content Bot started!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
