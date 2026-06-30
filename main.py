"""
YorTrade Content Automation Bot - Week 3
Fitur: Content history, multi-account selector, draft saving
"""

import asyncio
import logging
import os
import sqlite3
import anthropic
import fal_client
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
ANTHROPIC_API_KEY  = os.getenv('ANTHROPIC_API_KEY', '')
FAL_API_KEY        = os.getenv('FAL_API_KEY', '')
DB_PATH = 'yortrade.db'

os.environ['FAL_KEY'] = FAL_API_KEY

# ── States ───────────────────────────────────────────────────────────────────
WAITING_TOPIC            = 1
WAITING_REVISION         = 2
WAITING_VIDEO_CHOICE     = 3   # pilih video atau tidak
WAITING_POST_ACCOUNT     = 4   # pilih akun setelah video
WAITING_ADDACC_PLATFORM  = 5   # /addaccount step 1
WAITING_ADDACC_USERNAME  = 6   # /addaccount step 2

# ── Niche / Prompts ──────────────────────────────────────────────────────────
NICHES = {
    'trading'   : '📈 Trading',
    'affiliate' : '💰 Affiliate Marketing',
    'tech'      : '🤖 Tech/AI',
    'motivation': '💪 Motivasi/Mindset',
    'health'    : '🏥 Health & Fitness',
}

PLATFORM_EMOJI = {'instagram':'📸','tiktok':'🎵','youtube':'▶️','twitter':'🐦','other':'📱'}

VIDEO_STYLES = {
    'trading'   : 'professional trading desk, stock market charts, financial data, modern office, dynamic',
    'affiliate' : 'lifestyle product showcase, success story, modern aesthetics, energetic',
    'tech'      : 'futuristic technology, AI visualization, digital innovation, sleek design',
    'motivation': 'sunrise timelapse, person achieving goals, cinematic, inspirational',
    'health'    : 'healthy lifestyle, fitness, wellness, vibrant and energetic',
}

PROMPTS = {
    'trading': """Kamu adalah content creator trading profesional. Buat konten edukatif tentang: {topic}
Format:
JUDUL: [Judul menarik, max 10 kata]
CAPTION: [Caption 150-200 kata, engaging, pakai emoji, ada call-to-action]
HASHTAGS: [10-15 hashtag relevan]
Gunakan bahasa Indonesia yang santai tapi profesional.""",

    'affiliate': """Kamu adalah content creator affiliate marketing. Buat konten tentang: {topic}
Format:
JUDUL: [Judul menarik, max 10 kata]
CAPTION: [Caption 150-200 kata, persuasif, pakai emoji, highlight benefit]
HASHTAGS: [10-15 hashtag relevan]
Gunakan bahasa Indonesia yang engaging dan persuasif.""",

    'tech': """Kamu adalah content creator tech & AI. Buat konten edukasi tentang: {topic}
Format:
JUDUL: [Judul menarik, max 10 kata]
CAPTION: [Caption 150-200 kata, informatif, pakai emoji, mudah dipahami]
HASHTAGS: [10-15 hashtag relevan]
Gunakan bahasa Indonesia yang modern dan tech-savvy.""",

    'motivation': """Kamu adalah motivational content creator. Buat konten motivasi tentang: {topic}
Format:
JUDUL: [Judul menarik, max 10 kata]
CAPTION: [Caption 150-200 kata, inspiratif, pakai emoji, emosional]
HASHTAGS: [10-15 hashtag relevan]
Gunakan bahasa Indonesia yang memotivasi dan inspiring.""",

    'health': """Kamu adalah health & fitness content creator. Buat konten tentang: {topic}
Format:
JUDUL: [Judul menarik, max 10 kata]
CAPTION: [Caption 150-200 kata, informatif, pakai emoji, ada tips praktis]
HASHTAGS: [10-15 hashtag relevan]
Gunakan bahasa Indonesia yang informatif dan menyehatkan.""",
}

# ── Database ─────────────────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS content_history (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER NOT NULL,
        niche      TEXT,
        topic      TEXT,
        caption    TEXT,
        video_url  TEXT,
        status     TEXT DEFAULT 'draft',
        posted_to  TEXT,
        created_at TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_accounts (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    INTEGER NOT NULL,
        platform   TEXT,
        username   TEXT,
        created_at TEXT
    )''')
    conn.commit()
    conn.close()

def db_save_content(user_id, niche, topic, caption, video_url=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        'INSERT INTO content_history (user_id,niche,topic,caption,video_url,status,created_at) VALUES (?,?,?,?,?,?,?)',
        (user_id, niche, topic, caption, video_url, 'draft', datetime.now().strftime('%Y-%m-%d %H:%M'))
    )
    cid = c.lastrowid
    conn.commit(); conn.close()
    return cid

def db_mark_posted(content_id, account_label):
    conn = sqlite3.connect(DB_PATH)
    conn.execute('UPDATE content_history SET status=?,posted_to=? WHERE id=?',
                 ('posted', account_label, content_id))
    conn.commit(); conn.close()

def db_update_video(content_id, video_url):
    conn = sqlite3.connect(DB_PATH)
    conn.execute('UPDATE content_history SET video_url=? WHERE id=?', (video_url, content_id))
    conn.commit(); conn.close()

def db_get_history(user_id, limit=10):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        'SELECT id,niche,topic,status,posted_to,created_at FROM content_history WHERE user_id=? ORDER BY id DESC LIMIT ?',
        (user_id, limit)
    ).fetchall()
    conn.close()
    return rows

def db_get_content(content_id):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute('SELECT * FROM content_history WHERE id=?', (content_id,)).fetchone()
    conn.close()
    return row

def db_delete_content(content_id, user_id):
    conn = sqlite3.connect(DB_PATH)
    conn.execute('DELETE FROM content_history WHERE id=? AND user_id=?', (content_id, user_id))
    conn.commit(); conn.close()

def db_get_accounts(user_id):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute('SELECT id,platform,username FROM user_accounts WHERE user_id=?', (user_id,)).fetchall()
    conn.close()
    return rows

def db_add_account(user_id, platform, username):
    conn = sqlite3.connect(DB_PATH)
    conn.execute('INSERT INTO user_accounts (user_id,platform,username,created_at) VALUES (?,?,?,?)',
                 (user_id, platform, username, datetime.now().strftime('%Y-%m-%d %H:%M')))
    conn.commit(); conn.close()

def db_delete_account(account_id, user_id):
    conn = sqlite3.connect(DB_PATH)
    conn.execute('DELETE FROM user_accounts WHERE id=? AND user_id=?', (account_id, user_id))
    conn.commit(); conn.close()

# ── Claude helper ─────────────────────────────────────────────────────────────
async def generate_with_claude(niche, topic):
    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    prompt = PROMPTS.get(niche, PROMPTS['tech']).format(topic=topic)
    msg = await client.messages.create(
        model='claude-haiku-4-5-20251001', max_tokens=1024,
        messages=[{'role': 'user', 'content': prompt}]
    )
    return msg.content[0].text

async def generate_video_fal(niche, topic):
    style = VIDEO_STYLES.get(niche, VIDEO_STYLES.get('tech', ''))
    prompt = f"{topic}, {style}"
    handler = await fal_client.submit_async(
        "fal-ai/kling-video/v1/standard/text-to-video",
        arguments={"prompt": prompt, "duration": "5"}
    )
    result = await handler.get()
    return result['video']['url']

# ── /start & /help ────────────────────────────────────────────────────────────
async def start(update, context):
    u = update.effective_user
    await update.message.reply_text(
        f"👋 *Halo {u.first_name}!*\n\n"
        "Selamat datang di *YorTrade Content Bot* 🚀\n\n"
        "📝 /buat — Generate konten\n"
        "📋 /history — Lihat konten tersimpan\n"
        "➕ /addaccount — Tambah akun sosmed\n"
        "👥 /myaccounts — Lihat akun tersimpan\n"
        "❓ /help — Bantuan",
        parse_mode='Markdown')

async def help_command(update, context):
    await update.message.reply_text(
        "🤖 *YorTrade Content Bot — Help*\n\n"
        "📝 */buat* — Generate konten baru (caption + AI)\n"
        "📋 */history* — Lihat 10 konten terakhir\n"
        "➕ */addaccount* — Daftarkan akun IG/TikTok/YouTube\n"
        "👥 */myaccounts* — Lihat & hapus akun tersimpan\n"
        "❌ */cancel* — Batalkan proses\n\n"
        "🎯 *Alur:*\n"
        "1. /buat → pilih niche → ketik topik\n"
        "2. Review caption → Approve\n"
        "3. Pilih akun tujuan posting\n"
        "4. Konten tersimpan di /history",
        parse_mode='Markdown')

# ── /buat flow ────────────────────────────────────────────────────────────────
async def start_buat(update, context):
    kb = [[InlineKeyboardButton(name, callback_data=f"niche:{key}")] for key, name in NICHES.items()]
    await update.message.reply_text("🎯 *Pilih Niche Konten:*",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
    return WAITING_TOPIC

async def niche_selected(update, context):
    q = update.callback_query; await q.answer()
    key = q.data.replace('niche:', '')
    context.user_data.update({'niche': key, 'niche_name': NICHES.get(key, key)})
    await q.edit_message_text(f"✅ Niche: *{NICHES.get(key)}*\n\n📝 Ketik topiknya:",
        parse_mode='Markdown')
    return WAITING_TOPIC

async def topic_input(update, context):
    topic = update.message.text
    niche = context.user_data.get('niche', 'tech')
    niche_name = context.user_data.get('niche_name', 'Tech/AI')
    context.user_data['topic'] = topic

    loading = await update.message.reply_text(
        f"✍️ Generating *{niche_name}*...\nMohon tunggu!", parse_mode='Markdown')
    try:
        content = await generate_with_claude(niche, topic)
        context.user_data['generated_content'] = content
        await loading.delete()
        kb = [[
            InlineKeyboardButton("✅ Approve", callback_data="action:approve"),
            InlineKeyboardButton("✏️ Revisi",  callback_data="action:revise"),
            InlineKeyboardButton("🔄 Ulang",   callback_data="action:regenerate"),
        ]]
        preview = f"📋 *Preview Konten:*\n\n{content}"
        if len(preview) > 4000: preview = preview[:3997] + "..."
        await update.message.reply_text(preview, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
    except Exception as e:
        logger.error(e)
        await loading.edit_text(f"❌ Error: {e}\n\nCoba lagi dengan /buat")
    return WAITING_REVISION

async def handle_action(update, context):
    q = update.callback_query; await q.answer()
    action = q.data.replace('action:', '')
    niche   = context.user_data.get('niche', 'tech')
    topic   = context.user_data.get('topic', '')
    caption = context.user_data.get('generated_content', '')

    if action == 'approve':
            # Simpan ke DB dulu
            uid = update.effective_user.id
            cid = db_save_content(uid, niche, topic, caption)
            context.user_data['content_id'] = cid

            kb = [[
                InlineKeyboardButton("🎬 Generate Video", callback_data="video:yes"),
                InlineKeyboardButton("⏭️ Skip Video", callback_data="video:no"),
            ]]
            await q.edit_message_text(
                "✅ *Konten disimpan!* 🎉\n\nMau generate video AI buat konten ini? (FAL.AI Kling)",
                reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
            return WAITING_VIDEO_CHOICE

    elif action == 'revise':
        await q.edit_message_text("✏️ *Mode Revisi*\n\nKetik instruksi revisi kamu:", parse_mode='Markdown')
        return WAITING_REVISION

    elif action == 'regenerate':
        await q.edit_message_text(f"⏳ Regenerating...", parse_mode='Markdown')
        try:
            content = await generate_with_claude(niche, topic)
            context.user_data['generated_content'] = content
            kb = [[
                InlineKeyboardButton("✅ Approve", callback_data="action:approve"),
                InlineKeyboardButton("✏️ Revisi",  callback_data="action:revise"),
                InlineKeyboardButton("🔄 Ulang",   callback_data="action:regenerate"),
            ]]
            preview = f"📋 *Preview (Baru):*\n\n{content}"
            if len(preview) > 4000: preview = preview[:3997] + "..."
            await q.edit_message_text(preview, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
        except Exception as e:
            await q.edit_message_text(f"❌ Error: {e}\n\nKetik /buat")
            return ConversationHandler.END
    return WAITING_REVISION

async def handle_video_choice(update, context):
    q = update.callback_query; await q.answer()
    choice = q.data.replace('video:', '')
    uid = update.effective_user.id
    cid = context.user_data.get('content_id')
    niche = context.user_data.get('niche', 'tech')
    topic = context.user_data.get('topic', '')

    def _account_kb():
        accounts = db_get_accounts(uid)
        if not accounts:
            return None
        kb = [
            [InlineKeyboardButton(
                f"{PLATFORM_EMOJI.get(a[1],'📱')} @{a[2]} ({a[1].capitalize()})",
                callback_data=f"postto:{a[0]}:{a[2]}"
            )] for a in accounts
        ]
        kb.append([InlineKeyboardButton("💾 Simpan draf aja", callback_data="postto:draft:draft")])
        return InlineKeyboardMarkup(kb)

    if choice == 'yes':
        await q.edit_message_text("🎬 *Generating video...*\n\nProses 1-3 menit, mohon tunggu!", parse_mode='Markdown')
        try:
            video_url = await generate_video_fal(niche, topic)
            db_update_video(cid, video_url)
            await context.bot.send_video(chat_id=update.effective_chat.id, video=video_url, caption="🎬 Video berhasil dibuat!")
        except Exception as e:
            logger.error(e)
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"❌ Video generation gagal: {e}\n\nLanjut tanpa video aja ya.")
        markup = _account_kb()
        if markup:
            await context.bot.send_message(chat_id=update.effective_chat.id,
                text="Mau tandai posting ke akun mana?", reply_markup=markup, parse_mode='Markdown')
            return WAITING_POST_ACCOUNT
        else:
            caption = context.user_data.get('generated_content', '')
            await context.bot.send_message(chat_id=update.effective_chat.id,
                text="Belum ada akun tersimpan.\nTambah akun → /addaccount\nLihat konten → /history")
            await context.bot.send_message(chat_id=update.effective_chat.id, text=caption)
            context.user_data.clear()
            return ConversationHandler.END
    else:
        markup = _account_kb()
        if markup:
            await q.edit_message_text(
                "⏭️ *Skip video.*\n\nMau tandai posting ke akun mana?",
                reply_markup=markup, parse_mode='Markdown')
            return WAITING_POST_ACCOUNT
        else:
            caption = context.user_data.get('generated_content', '')
            await q.edit_message_text(
                "✅ *Konten disimpan sebagai draft!* 💾\n\nBelum ada akun tersimpan.\nTambah akun → /addaccount\nLihat konten → /history",
                parse_mode='Markdown')
            await context.bot.send_message(chat_id=update.effective_chat.id, text=caption)
            context.user_data.clear()
            return ConversationHandler.END

async def revision_input(update, context):
    revision = update.message.text
    original = context.user_data.get('generated_content', '')
    loading = await update.message.reply_text("⏳ Merevisi...")
    try:
        client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
        prompt = f"Revisi konten ini:\n\nKONTEN:\n{original}\n\nINSTRUKSI: {revision}\n\nBerikan hasil revisi dalam format yang sama (JUDUL, CAPTION, HASHTAGS)."
        msg = await client.messages.create(
            model='claude-haiku-4-5-20251001', max_tokens=1024,
            messages=[{'role': 'user', 'content': prompt}]
        )
        revised = msg.content[0].text
        context.user_data['generated_content'] = revised
        await loading.delete()
        kb = [[
            InlineKeyboardButton("✅ Approve",    callback_data="action:approve"),
            InlineKeyboardButton("✏️ Revisi Lagi",callback_data="action:revise"),
            InlineKeyboardButton("🔄 Ulang",      callback_data="action:regenerate"),
        ]]
        preview = f"📋 *Preview (Revisi):*\n\n{revised}"
        if len(preview) > 4000: preview = preview[:3997] + "..."
        await update.message.reply_text(preview, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
    except Exception as e:
        await loading.edit_text(f"❌ Error: {e}")
    return WAITING_REVISION

async def handle_post_account(update, context):
    q = update.callback_query; await q.answer()
    parts = q.data.replace('postto:', '').split(':')
    acc_id, acc_name = parts[0], parts[1]
    cid = context.user_data.get('content_id')
    caption = context.user_data.get('generated_content', '')

    if acc_id == 'draft':
        await q.edit_message_text(
            "💾 *Disimpan sebagai draft!*\n\nLihat di /history kapanpun.", parse_mode='Markdown')
    else:
        label = f"@{acc_name}"
        db_mark_posted(cid, label)
        await q.edit_message_text(
            f"📌 *Ditandai: post ke {label}*\n\n"
            "Caption sudah disalin di bawah — tinggal paste ke platform!\n\n"
            "Lihat semua konten → /history",
            parse_mode='Markdown')

    # Kirim caption sebagai pesan plain (mudah di-copy)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=caption)
    context.user_data.clear()
    return ConversationHandler.END

# ── /history ──────────────────────────────────────────────────────────────────
async def history_command(update, context):
    uid = update.effective_user.id
    rows = db_get_history(uid)
    if not rows:
        await update.message.reply_text("📋 Belum ada konten tersimpan.\n\nGenerate dengan /buat!")
        return

    niche_emoji = {'trading':'📈','affiliate':'💰','tech':'🤖','motivation':'💪','health':'🏥'}
    text = "📋 *10 Konten Terakhir:*\n\n"
    kb = []
    for r in rows:
        rid, niche, topic, status, posted_to, created = r
        emoji = niche_emoji.get(niche, '📝')
        status_icon = '✅' if status == 'posted' else '💾'
        posted_info = f" → {posted_to}" if posted_to else ''
        text += f"{status_icon} *#{rid}* {emoji} {topic[:30]}\n_{created}{posted_info}_\n\n"
        kb.append([InlineKeyboardButton(f"#{rid} {topic[:25]}...", callback_data=f"hist:{rid}")])

    kb.append([InlineKeyboardButton("🗑 Hapus semua draft", callback_data="hist:clearall")])
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

async def history_item(update, context):
    q = update.callback_query; await q.answer()
    data = q.data.replace('hist:', '')
    uid = update.effective_user.id

    if data == 'clearall':
        conn = sqlite3.connect(DB_PATH)
        conn.execute("DELETE FROM content_history WHERE user_id=? AND status='draft'", (uid,))
        conn.commit(); conn.close()
        await q.edit_message_text("🗑 Semua draft dihapus!", parse_mode='Markdown')
        return

    row = db_get_content(int(data))
    if not row:
        await q.edit_message_text("❌ Konten tidak ditemukan.")
        return

    rid, uid2, niche, topic, caption, video_url, status, posted_to, created = row
    niche_emoji = {'trading':'📈','affiliate':'💰','tech':'🤖','motivation':'💪','health':'🏥'}
    status_text = f"✅ Posted ke {posted_to}" if status == 'posted' else "💾 Draft"

    preview = f"*#{rid} — {niche_emoji.get(niche,'📝')} {topic}*\n_{created}_\nStatus: {status_text}\n\n{caption}"
    if len(preview) > 4000: preview = preview[:3997] + "..."

    kb = [
        [InlineKeyboardButton("📋 Copy caption (resend)", callback_data=f"histcopy:{rid}")],
        [InlineKeyboardButton("🗑 Hapus", callback_data=f"histdel:{rid}")],
        [InlineKeyboardButton("← Kembali", callback_data="hist:back")],
    ]
    await q.edit_message_text(preview, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

async def history_copy(update, context):
    q = update.callback_query; await q.answer()
    rid = int(q.data.replace('histcopy:', ''))
    row = db_get_content(rid)
    if row:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=row[4])
        await q.answer("Caption dikirim ulang!", show_alert=False)

async def history_delete(update, context):
    q = update.callback_query; await q.answer()
    rid = int(q.data.replace('histdel:', ''))
    db_delete_content(rid, update.effective_user.id)
    await q.edit_message_text(f"🗑 Konten #{rid} dihapus.\n\nKembali ke /history")

# ── /addaccount flow ──────────────────────────────────────────────────────────
async def addaccount_start(update, context):
    kb = [
        [InlineKeyboardButton("📸 Instagram", callback_data="addacc:instagram")],
        [InlineKeyboardButton("🎵 TikTok",    callback_data="addacc:tiktok")],
        [InlineKeyboardButton("▶️ YouTube",   callback_data="addacc:youtube")],
        [InlineKeyboardButton("🐦 Twitter/X", callback_data="addacc:twitter")],
        [InlineKeyboardButton("📱 Lainnya",   callback_data="addacc:other")],
    ]
    await update.message.reply_text("➕ *Tambah Akun Sosmed*\n\nPilih platform:",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
    return WAITING_ADDACC_PLATFORM

async def addaccount_platform(update, context):
    q = update.callback_query; await q.answer()
    platform = q.data.replace('addacc:', '')
    context.user_data['new_platform'] = platform
    names = {'instagram':'Instagram','tiktok':'TikTok','youtube':'YouTube','twitter':'Twitter/X','other':'Lainnya'}
    await q.edit_message_text(
        f"{PLATFORM_EMOJI.get(platform)} Platform: *{names[platform]}*\n\nMasukkan username (tanpa @):",
        parse_mode='Markdown')
    return WAITING_ADDACC_USERNAME

async def addaccount_username(update, context):
    username = update.message.text.strip().lstrip('@')
    platform = context.user_data.get('new_platform', 'other')
    uid = update.effective_user.id
    db_add_account(uid, platform, username)
    emoji = PLATFORM_EMOJI.get(platform, '📱')
    await update.message.reply_text(
        f"✅ Akun *{emoji} @{username}* berhasil ditambahkan!\n\n"
        "Sekarang setiap konten yang di-approve bisa langsung\n"
        f"ditandai posting ke akun ini.\n\n"
        "Tambah akun lain → /addaccount\n"
        "Lihat akun → /myaccounts",
        parse_mode='Markdown')
    context.user_data.clear()
    return ConversationHandler.END

async def myaccounts_command(update, context):
    uid = update.effective_user.id
    accounts = db_get_accounts(uid)
    if not accounts:
        await update.message.reply_text(
            "👥 Belum ada akun tersimpan.\n\nTambah dengan /addaccount!")
        return
    kb = [[InlineKeyboardButton(
        f"{PLATFORM_EMOJI.get(a[1],'📱')} @{a[2]} ({a[1]}) — 🗑 hapus",
        callback_data=f"delacc:{a[0]}")] for a in accounts]
    text = "👥 *Akun Tersimpan:*\n\n" + "\n".join(
        [f"{PLATFORM_EMOJI.get(a[1],'📱')} @{a[2]} ({a[1].capitalize()})" for a in accounts])
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

async def delete_account(update, context):
    q = update.callback_query; await q.answer()
    acc_id = int(q.data.replace('delacc:', ''))
    db_delete_account(acc_id, update.effective_user.id)
    await q.edit_message_text("🗑 Akun dihapus.\n\nLihat akun → /myaccounts")

async def cancel(update, context):
    await update.message.reply_text("❌ Dibatalkan. Ketik /buat untuk mulai lagi.")
    context.user_data.clear()
    return ConversationHandler.END

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN tidak di-set!"); return
    if not ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY tidak di-set!"); return

    init_db()
    logger.info("Database initialized.")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Conversation: /buat flow
    buat_handler = ConversationHandler(
        entry_points=[CommandHandler('buat', start_buat)],
        states={
            WAITING_TOPIC: [
                CallbackQueryHandler(niche_selected, pattern='^niche:'),
                MessageHandler(filters.TEXT & ~filters.COMMAND, topic_input),
            ],
            WAITING_REVISION: [
                CallbackQueryHandler(handle_action, pattern='^action:'),
                MessageHandler(filters.TEXT & ~filters.COMMAND, revision_input),
            ],
            WAITING_VIDEO_CHOICE: [
                CallbackQueryHandler(handle_video_choice, pattern='^video:'),
            ],
            WAITING_POST_ACCOUNT: [
                CallbackQueryHandler(handle_post_account, pattern='^postto:'),
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    # Conversation: /addaccount flow
    addacc_handler = ConversationHandler(
        entry_points=[CommandHandler('addaccount', addaccount_start)],
        states={
            WAITING_ADDACC_PLATFORM: [CallbackQueryHandler(addaccount_platform, pattern='^addacc:')],
            WAITING_ADDACC_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, addaccount_username)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(CommandHandler('myaccounts', myaccounts_command))
    app.add_handler(CommandHandler('history', history_command))
    app.add_handler(buat_handler)
    app.add_handler(addacc_handler)

    # Callback handlers untuk history & account delete (di luar conversation)
    app.add_handler(CallbackQueryHandler(history_item,   pattern='^hist:'))
    app.add_handler(CallbackQueryHandler(history_copy,   pattern='^histcopy:'))
    app.add_handler(CallbackQueryHandler(history_delete, pattern='^histdel:'))
    app.add_handler(CallbackQueryHandler(delete_account, pattern='^delacc:'))

    logger.info("YorTrade Bot started! Week 3 features active.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
