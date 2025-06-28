import os
import logging
import asyncio
import sqlite3
import nest_asyncio
from datetime import datetime

from dotenv import load_dotenv
from telegram import (
    Update, InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ChatJoinRequestHandler, ContextTypes, MessageHandler, filters
)
from telegram.constants import ParseMode
from telegram.error import Forbidden, TelegramError

# -------------------------------------------
# ✅ Load .env file 
# -------------------------------------------
load_dotenv()
nest_asyncio.apply()

# ------------------------
# CONFIGURATION (.env से)
# ------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
MAIN_CHANNEL_LINK = os.getenv("MAIN_CHANNEL_LINK", "https://t.me/YOUR_CHANNEL")
DB_FILE = "bot_users.db"

# ------------------------
# LOGGER
# ------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ------------------------
# DATABASE INIT
# ------------------------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_blocked INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


def add_or_update_user(user_id, username, first_name):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO users (user_id, username, first_name, last_seen, is_blocked)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP, 0)
    """, (user_id, username, first_name))
    conn.commit()
    conn.close()


def get_active_users():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE is_blocked = 0")
    users = [row[0] for row in cur.fetchall()]
    conn.close()
    return users


def block_user(user_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("UPDATE users SET is_blocked = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def clean_blocked():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE is_blocked = 1")
    deleted = cur.rowcount
    conn.commit()
    conn.close()
    return deleted


def get_stats():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM users WHERE is_blocked = 0")
    active = cur.fetchone()[0]
    blocked = total - active
    return total, active, blocked


# ------------------------
# BOT HANDLERS
# ------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_or_update_user(user.id, user.username, user.first_name)

    if user.id == ADMIN_ID:
        await show_admin_panel(update, context)
    else:
        keyboard = [
            [InlineKeyboardButton("➕ Add Me To Channel", url=f"https://t.me/Auto_request_bot?startchannel=Bots4Sale&admin=invite_users+manage_chat")],
[InlineKeyboardButton("➕ Add Me To Group", url=f"https://t.me/Auto_request_bot?startgroup=Bots4Sale&admin=invite_users+manage_chat")],
        ]
        text = (
            f"👋 **Hi {user.first_name}**\n\n"
            f"🤖 *Give Me Admin In Your Channel To Accept Join Requests Automatically!*\n\n"
        )
        await update.message.reply_text(
            text, reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )


async def handle_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.chat_join_request.from_user
    chat = update.chat_join_request.chat

    try:
        await context.bot.approve_chat_join_request(chat.id, user.id)
        add_or_update_user(user.id, user.username, user.first_name)

        welcome = f"Hello {user.first_name}, your request to join {chat.title} has been approved!\nSend /start to know more."

        keyboard = [
            [InlineKeyboardButton("➕ Add Me To Channel", url=f"https://t.me/Auto_request_bot?startchannel=Bots4Sale&admin=invite_users+manage_chat")],
[InlineKeyboardButton("➕ Add Me To Group", url=f"https://t.me/Auto_request_bot?startgroup=Bots4Sale&admin=invite_users+manage_chat")],
        ]

        try:
            await context.bot.send_message(
                chat_id=user.id,
                text=welcome,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Forbidden:
            logger.info(f"User {user.id} blocked bot or never started")

    except TelegramError as e:
        logger.error(f"Error approving join request: {e}")


async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    total, active, blocked = get_stats()
    keyboard = [
        [InlineKeyboardButton("📤 Broadcast", callback_data="broadcast")],
        [InlineKeyboardButton("🗑️ Clean Blocked", callback_data="clean_db")],
    ]
    text = (
        f"🔧 **Admin Panel**\n\n"
        f"👥 *Total Users:* `{total}`\n"
        f"✅ *Active:* `{active}`\n"
        f"🚫 *Blocked:* `{blocked}`\n"
    )
    await update.message.reply_text(
        text, reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )


async def admin_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if user_id != ADMIN_ID:
        await query.answer("❌ Not allowed!", show_alert=True)
        return

    if query.data == "broadcast":
        await query.edit_message_text("📢 *Send your broadcast message now...*", parse_mode=ParseMode.MARKDOWN)
        context.user_data["broadcast"] = True

    elif query.data == "clean_db":
        deleted = clean_blocked()
        await query.edit_message_text(f"🧹 Cleaned {deleted} blocked users.")


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not context.user_data.get("broadcast"):
        return

    context.user_data["broadcast"] = False

    msg = update.message
    text = msg.text or msg.caption or ""

    success = 0
    failed = 0

    users = get_active_users()
    for user_id in users:
        try:
            if msg.photo:
                await context.bot.send_photo(user_id, msg.photo[-1].file_id, caption=text)
            elif msg.video:
                await context.bot.send_video(user_id, msg.video.file_id, caption=text)
            elif msg.document:
                await context.bot.send_document(user_id, msg.document.file_id, caption=text)
            else:
                await context.bot.send_message(user_id, text)
            success += 1
        except Forbidden:
            block_user(user_id)
            failed += 1
        except TelegramError:
            failed += 1

    await update.message.reply_text(
        f"✅ Broadcast done!\nSent: {success}\nFailed: {failed}"
    )


# ------------------------
# MAIN
# ------------------------
async def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(ChatJoinRequestHandler(handle_join_request))
    app.add_handler(CallbackQueryHandler(admin_buttons))
    app.add_handler(MessageHandler(filters.ALL, broadcast))

    await app.run_polling()


if __name__ == "__main__":
    asyncio.run(main())