"""
YorTrade Content Automation Bot - With FAL.AI Video Generation
Week 2: Generate teks + video otomatis via Kling AI
"""

import asyncio
import logging
import os
import anthropic
import fal_client
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
FAL_API_KEY = os.getenv('FAL_API_KEY', '')

# Set FAL key untuk library
os.environ['FAL_KEY'] = FAL_API_KEY

# Conversation states
WAITING_TOPIC = 1
WAITING_REVISION = 2
WAITING_VIDEO = 3

# Definisi niche
NICHES = {
    'trading': 'Trading',
    'affiliate': 'Affiliate Marketing',
    'tech': 'Tech/AI',
    'motivation': 'Motivasi/Mindset',
    'health': 'Health & Fitness'
}

# Video style per niche untuk Kling prompt
VIDEO_STYLES = {
    'trading': 'professional trading desk, stock market charts moving, financial data visualization, modern office, dynamic camera movement',
    'affiliate': 'lifestyle product showcase, success story, modern aesthetics, testimonial style, energetic',
    'tech': 'futuristic technology, AI visualization, digital data streams, innovation, sleek modern design',
    'motivation': 'sunrise timelapse, person achieving goals, success montage, inspirational journey, cinematic',
    'health': 'healthy lifestyle, morning workout, fresh vegetables, wellness routine, energetic and vibrant'
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


# ─── Helper Functions ──────────────────────────────────────────────

async def generate_with_claude(niche, topic):
    """Generate teks konten via Claude Haiku."""
    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    prompt = PROMPTS.get(niche, PROMPTS['tech']).format(topic=topic)
    message = await client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text


async def generate_video_fal(niche, topic, content):
    """Generate video 9:16 via FAL.AI Kling 2.5."""
    # Ambil judul dari konten yang di-generate
    judul = topic
    for line in content.split('\n'):
        if line.strip().startswith('JUDUL:'):
            judul = line.replace('JUDUL:', '').strip()
            break

    style = VIDEO_STYLES.get(niche, 'professional, modern, engaging')
    prompt = (
        f"Short vertical social media video (9:16) about: {judul}. "
        f"Visual style: {style}. "
        f"High quality, cinematic, engaging for TikTok and Instagram Reels."
    )

    logger.info(f"Generating video with prompt: {prompt[:100]}...")

    # Run fal_client di thread terpisah (sync → async)
    result = await asyncio.to_thread(
        fal_client.run,
        "fal-ai/kling-video/v1.6/standard/text-to-video",
        arguments={
            "prompt": prompt,
            "duration": "5",
            "aspect_ratio": "9:16"
        }
    )

    video_url = result['video']['url']
    logger.info(f"Video generated: {video_url}")
    return video_url


# ─── Bot Handlers ──────────────────────────────────────────────────

async def start(update, context):
    user = update.effective_user
    await update.message.reply_text(
        f"👋 *Halo {user.first_name}!*\n\n"
        "Selamat datang di *YorTrade Content Bot* 🚀\n\n"
        "Bot ini bisa generate:\n"
        "📝 Caption + Hashtag otomatis\n"
        "🎬 Video 9:16 via Kling AI (opsional)\n\n"
        "Ketik /buat untuk mulai!",
        parse_mode='Markdown'
    )


async def help_command(update, context):
    await update.message.reply_text(
        "🤖 *YorTrade Content Bot*\n\n"
        "📝 *Commands:*\n"
        "/start — Mulai bot\n"
        "/buat — Generate konten baru\n"
        "/cancel — Batalkan proses\n\n"
        "🎯 *Cara Pakai:*\n"
        "1. Ketik /buat\n"
        "2. Pilih niche konten\n"
        "3. Masukkan topik\n"
        "4. Review & approve caption\n"
        "5. Pilih: generate video atau tidak",
        parse_mode='Markdown'
    )


async def start_buat(update, context):
    keyboard = [
        [InlineKeyboardButton(f"📈 Trading", callback_data="niche:trading")],
        [InlineKeyboardButton(f"💰 Affiliate Marketing", callback_data="niche:affiliate")],
        [InlineKeyboardButton(f"🤖 Tech/AI", callback_data="niche:tech")],
        [InlineKeyboardButton(f"💪 Motivasi/Mindset", callback_data="niche:motivation")],
        [InlineKeyboardButton(f"🏥 Health & Fitness", callback_data="niche:health")]
    ]
    await update.message.reply_text(
        "🎯 *Pilih Niche Konten:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return WAITING_TOPIC


async def niche_selected(update, context):
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
    topic = update.message.text
    niche = context.user_data.get('niche', 'tech')
    niche_name = context.user_data.get('niche_name', 'Tech/AI')
    context.user_data['topic'] = topic

    loading_msg = await update.message.reply_text(
        f"✍️ Generating caption *{niche_name}*...\n\nMohon tunggu sebentar!",
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
    query = update.callback_query
    await query.answer()
    action = query.data.replace("action:", "")

    if action == "approve":
        # Tanya mau generate video juga ga
        keyboard = [[
            InlineKeyboardButton("🎬 Ya, bikin video!", callback_data="video:yes"),
            InlineKeyboardButton("📋 Tidak, caption aja", callback_data="video:no")
        ]]
        await query.edit_message_text(
            "✅ *Caption Approved!* 🎉\n\n"
            "Mau generate *video 9:16* juga? 🎬\n"
            "_(Kling AI — format TikTok/Reels/Shorts)_\n\n"
            "⏱ Proses: 1-3 menit\n"
            "💰 Cost: ~$0.50 per video",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        return WAITING_VIDEO

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
            f"⏳ Regenerating *{niche_name}*...",
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


async def handle_video_choice(update, context):
    """Handle pilihan generate video atau tidak."""
    query = update.callback_query
    await query.answer()
    choice = query.data.replace("video:", "")

    if choice == "no":
        content = context.user_data.get('generated_content', '')
        # Kirim caption sebagai pesan terpisah biar gampang di-copy
        await query.edit_message_text(
            "📋 *Caption siap!* Tinggal copy-paste ke sosmed.\n\nMau generate lagi? Ketik /buat",
            parse_mode='Markdown'
        )
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=content
        )
        context.user_data.clear()
        return ConversationHandler.END

    elif choice == "yes":
        niche = context.user_data.get('niche', 'tech')
        topic = context.user_data.get('topic', '')
        content = context.user_data.get('generated_content', '')

        await query.edit_message_text(
            "🎬 *Generating video...*\n\n"
            "Kling AI lagi bikin videonya, estimasi *1-3 menit* ya!\n\n"
            "☕ Santai dulu, gue kabarin kalau udah jadi.",
            parse_mode='Markdown'
        )

        try:
            video_url = await generate_video_fal(niche, topic, content)

            # Kirim video ke user
            await context.bot.send_video(
                chat_id=update.effective_chat.id,
                video=video_url,
                caption=(
                    "🎬 *Video siap bro!*\n\n"
                    "Download dan posting ke TikTok/IG/Shorts!\n\n"
                    "Mau generate lagi? Ketik /buat"
                ),
                parse_mode='Markdown'
            )

            # Kirim caption juga biar gampang di-copy
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"📋 *Caption-nya:*\n\n{content}",
                parse_mode='Markdown'
            )

        except Exception as e:
            logger.error(f"Error generating video: {e}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=(
                    f"❌ *Gagal generate video:* {str(e)}\n\n"
                    "Caption tetap bisa dipakai ya!\n"
                    "Coba lagi nanti dengan /buat"
                ),
                parse_mode='Markdown'
            )

        context.user_data.clear()
        return ConversationHandler.END

    return WAITING_VIDEO


async def revision_input(update, context):
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

        preview = f"📋 *Preview (Revisi):*\n\n{revised}"
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
    await update.message.reply_text("❌ Dibatalkan. Ketik /buat untuk mulai lagi.")
    context.user_data.clear()
    return ConversationHandler.END


# ─── Main ──────────────────────────────────────────────────────────

def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN tidak di-set!")
        return
    if not ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY tidak di-set!")
        return
    if not FAL_API_KEY:
        logger.warning("FAL_API_KEY tidak di-set — video generation tidak akan berfungsi!")

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
            ],
            WAITING_VIDEO: [
                CallbackQueryHandler(handle_video_choice, pattern="^video:")
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(conv_handler)

    logger.info("YorTrade Content Bot (with FAL.AI) started!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
