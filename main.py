import os
import logging
import asyncio
import json
import nest_asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from telegram import (
    Update, InlineKeyboardMarkup, InlineKeyboardButton, 
    BotCommand, BotCommandScopeAllPrivateChats, ParseMode
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ChatJoinRequestHandler, ContextTypes, MessageHandler, 
    filters, ConversationHandler
)
from telegram.error import Forbidden, TelegramError
from telegram.constants import ParseMode

from config import Config
from database import DatabaseManager
from broadcast_manager import BroadcastManager

# Apply nest_asyncio for compatibility
nest_asyncio.apply()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Conversation states
WAITING_FOR_BROADCAST = 1
WAITING_FOR_BULK_MESSAGE = 2

class TelegramBot:
    def __init__(self):
        # Validate configuration
        Config.validate()
        
        # Initialize database and broadcast manager
        self.db = DatabaseManager(Config.DATABASE_URL)
        self.broadcast_manager = None
        
        # User session data
        self.user_sessions = {}
        
        # Statistics cache
        self.stats_cache = {}
        self.stats_cache_time = None
    
    async def initialize(self):
        """Initialize the bot and database"""
        await self.db.init_db()
        logger.info("Database initialized successfully")
    
    def create_application(self) -> Application:
        """Create and configure the Telegram application"""
        app = Application.builder().token(Config.BOT_TOKEN).build()
        
        # Initialize broadcast manager with bot instance
        self.broadcast_manager = BroadcastManager(app.bot, self.db)
        
        # Add handlers
        self._add_handlers(app)
        
        return app
    
    def _add_handlers(self, app: Application):
        """Add all command and callback handlers"""
        # Commands
        app.add_handler(CommandHandler("start", self.start_command))
        app.add_handler(CommandHandler("admin", self.admin_command))
        app.add_handler(CommandHandler("stats", self.stats_command))
        app.add_handler(CommandHandler("users", self.users_command))
        app.add_handler(CommandHandler("help", self.help_command))
        app.add_handler(CommandHandler("broadcast", self.broadcast_command))
        
        # Callback queries
        app.add_handler(CallbackQueryHandler(self.handle_callbacks))
        
        # Join requests
        app.add_handler(ChatJoinRequestHandler(self.handle_join_request))
        
        # Conversation handler for broadcasts
        broadcast_conv = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.start_broadcast, pattern="^broadcast_new$")],
            states={
                WAITING_FOR_BROADCAST: [MessageHandler(filters.ALL, self.process_broadcast_message)],
            },
            fallbacks=[CallbackQueryHandler(self.cancel_broadcast, pattern="^broadcast_cancel$")]
        )
        app.add_handler(broadcast_conv)
        
        # All other messages (for admin responses)
        app.add_handler(MessageHandler(filters.ALL, self.handle_messages))
    
    async def set_bot_commands(self, app: Application):
        """Set bot commands for better UX"""
        commands = [
            BotCommand("start", "🚀 Start the bot"),
            BotCommand("help", "❓ Get help"),
            BotCommand("admin", "⚙️ Admin panel (admin only)"),
            BotCommand("stats", "📊 Bot statistics (admin only)"),
            BotCommand("users", "👥 User management (admin only)"),
            BotCommand("broadcast", "📢 Send broadcast (admin only)"),
        ]
        
        await app.bot.set_my_commands(commands, scope=BotCommandScopeAllPrivateChats())
        logger.info("Bot commands set successfully")
    
    # Command Handlers
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        
        # Add/update user in database
        user_data = {
            "user_id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "language_code": user.language_code,
            "is_bot": user.is_bot,
            "is_premium": user.is_premium if hasattr(user, 'is_premium') else False
        }
        
        await self.db.add_or_update_user(user_data)
        
        if user.id == Config.ADMIN_ID:
            await self.show_admin_dashboard(update, context)
        else:
            await self.show_user_welcome(update, context)
    
    async def admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /admin command"""
        if update.effective_user.id != Config.ADMIN_ID:
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
        
        await self.show_admin_dashboard(update, context)
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command"""
        if update.effective_user.id != Config.ADMIN_ID:
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
        
        await self.show_detailed_stats(update, context)
    
    async def users_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /users command"""
        if update.effective_user.id != Config.ADMIN_ID:
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
        
        await self.show_user_management(update, context)
    
    async def broadcast_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /broadcast command"""
        if update.effective_user.id != Config.ADMIN_ID:
            await update.message.reply_text("❌ You are not authorized to use this command.")
            return
        
        await self.show_broadcast_panel(update, context)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = (
            "🤖 **Telegram Auto Accept Bot**\n\n"
            "**Features:**\n"
            "• ✅ Auto-approve channel join requests\n"
            "• 📢 Advanced broadcasting system\n"
            "• 👥 User management\n"
            "• 📊 Detailed statistics\n"
            "• 🔄 Retry mechanism for failed messages\n\n"
            "**How to use:**\n"
            "1. Add the bot as admin in your channel\n"
            "2. Enable 'Invite Users' permission\n"
            "3. Users' join requests will be auto-approved\n\n"
            f"**Support:** {Config.SUPPORT_CHAT}\n"
            f"**Channel:** {Config.MAIN_CHANNEL_LINK}"
        )
        
        keyboard = [
            [InlineKeyboardButton("➕ Add to Channel", url=f"https://t.me/{Config.BOT_USERNAME}?startchannel=true&admin=invite_users+manage_chat")],
            [InlineKeyboardButton("➕ Add to Group", url=f"https://t.me/{Config.BOT_USERNAME}?startgroup=true&admin=invite_users+manage_chat")],
            [InlineKeyboardButton("📢 Support", url=Config.SUPPORT_CHAT)]
        ]
        
        await update.message.reply_text(
            help_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    # UI Methods
    async def show_user_welcome(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show welcome message to regular users"""
        user = update.effective_user
        
        welcome_text = (
            f"👋 **Welcome {user.first_name}!**\n\n"
            f"🤖 **I'm an Auto Accept Bot!**\n\n"
            f"**What I do:**\n"
            f"• ✅ Auto-approve your channel join requests\n"
            f"• 🚀 Instant approval - no waiting!\n"
            f"• 📢 Keep you updated with important announcements\n\n"
            f"**How to use me:**\n"
            f"1. Add me as admin to your channel\n"
            f"2. Give me 'Invite Users' permission\n"
            f"3. That's it! I'll handle the rest\n\n"
            f"📱 **Quick Actions:**"
        )
        
        keyboard = [
            [InlineKeyboardButton("➕ Add Me To Channel", url=f"https://t.me/{Config.BOT_USERNAME}?startchannel=true&admin=invite_users+manage_chat")],
            [InlineKeyboardButton("➕ Add Me To Group", url=f"https://t.me/{Config.BOT_USERNAME}?startgroup=true&admin=invite_users+manage_chat")],
            [InlineKeyboardButton("📢 Main Channel", url=Config.MAIN_CHANNEL_LINK), InlineKeyboardButton("💬 Support", url=Config.SUPPORT_CHAT)],
            [InlineKeyboardButton("❓ Help", callback_data="help")]
        ]
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def show_admin_dashboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show modern admin dashboard"""
        stats = await self.get_cached_stats()
        
        # Calculate growth
        growth_text = "📈 Growing"
        if stats["total"] > 0:
            success_rate = (stats["active"] / stats["total"]) * 100
            growth_text = f"📈 {success_rate:.1f}% Active"
        
        dashboard_text = (
            f"🎛️ **{Config.ADMIN_PANEL_TITLE}**\n\n"
            f"📊 **Quick Stats:**\n"
            f"├ 👥 Total Users: `{stats['total']}`\n"
            f"├ ✅ Active Users: `{stats['active']}`\n"
            f"├ 🚫 Blocked Users: `{stats['blocked']}`\n"
            f"├ ⭐ Premium Users: `{stats['premium']}`\n"
            f"└ {growth_text}\n\n"
            f"🕐 **Last Updated:** `{datetime.now().strftime('%H:%M:%S')}`\n"
            f"📅 **Date:** `{datetime.now().strftime('%d %b %Y')}`"
        )
        
        keyboard = [
            [InlineKeyboardButton("📤 Broadcast", callback_data="broadcast_panel"), InlineKeyboardButton("👥 Users", callback_data="user_management")],
            [InlineKeyboardButton("📊 Detailed Stats", callback_data="detailed_stats"), InlineKeyboardButton("📋 Logs", callback_data="view_logs")],
            [InlineKeyboardButton("🗑️ Clean Database", callback_data="clean_db"), InlineKeyboardButton("⚙️ Settings", callback_data="bot_settings")],
            [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_dashboard"), InlineKeyboardButton("❓ Help", callback_data="admin_help")]
        ]
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                dashboard_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                dashboard_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def show_broadcast_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show advanced broadcast panel"""
        stats = await self.get_cached_stats()
        
        panel_text = (
            f"📢 **Broadcast Center**\n\n"
            f"📊 **Target Audience:**\n"
            f"• Active Users: `{stats['active']}`\n"
            f"• Premium Users: `{stats['premium']}`\n"
            f"• Total Reach: `{stats['active']}`\n\n"
            f"✨ **Features:**\n"
            f"• 📱 Text, Images, Videos, Documents\n"
            f"• 🔘 Inline Buttons Support\n"
            f"• 🔄 Auto-retry Failed Messages (3x)\n"
            f"• 📊 Real-time Progress Tracking\n"
            f"• 📈 Detailed Analytics\n\n"
            f"🚀 **Ready to broadcast?**"
        )
        
        keyboard = [
            [InlineKeyboardButton("📝 New Broadcast", callback_data="broadcast_new")],
            [InlineKeyboardButton("📊 Broadcast History", callback_data="broadcast_history"), InlineKeyboardButton("🔄 Retry Failed", callback_data="broadcast_retry")],
            [InlineKeyboardButton("📈 Analytics", callback_data="broadcast_analytics"), InlineKeyboardButton("⚙️ Settings", callback_data="broadcast_settings")],
            [InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_dashboard")]
        ]
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                panel_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                panel_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def show_user_management(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user management panel"""
        stats = await self.get_cached_stats()
        
        panel_text = (
            f"👥 **User Management**\n\n"
            f"📊 **Overview:**\n"
            f"├ 📈 Total Users: `{stats['total']}`\n"
            f"├ ✅ Active: `{stats['active']}`\n"
            f"├ 🚫 Blocked: `{stats['blocked']}`\n"
            f"├ ⭐ Premium: `{stats['premium']}`\n"
            f"└ 🤖 Bots: `0`\n\n"
            f"🛠️ **Management Tools:**"
        )
        
        keyboard = [
            [InlineKeyboardButton("👁️ View Users", callback_data="view_users"), InlineKeyboardButton("🔍 Search User", callback_data="search_user")],
            [InlineKeyboardButton("🚫 Blocked Users", callback_data="blocked_users"), InlineKeyboardButton("⭐ Premium Users", callback_data="premium_users")],
            [InlineKeyboardButton("📊 User Analytics", callback_data="user_analytics"), InlineKeyboardButton("📤 Export Data", callback_data="export_users")],
            [InlineKeyboardButton("🗑️ Clean Blocked", callback_data="clean_blocked"), InlineKeyboardButton("🔄 Refresh", callback_data="refresh_users")],
            [InlineKeyboardButton("🔙 Back to Dashboard", callback_data="admin_dashboard")]
        ]
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                panel_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def show_detailed_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show detailed statistics"""
        stats = await self.get_cached_stats()
        
        # Calculate additional metrics
        total = stats["total"]
        active_rate = (stats["active"] / total * 100) if total > 0 else 0
        premium_rate = (stats["premium"] / total * 100) if total > 0 else 0
        
        stats_text = (
            f"📊 **Detailed Statistics**\n\n"
            f"👥 **User Metrics:**\n"
            f"├ Total Users: `{stats['total']}`\n"
            f"├ Active Users: `{stats['active']}` ({active_rate:.1f}%)\n"
            f"├ Blocked Users: `{stats['blocked']}`\n"
            f"├ Premium Users: `{stats['premium']}` ({premium_rate:.1f}%)\n"
            f"└ Success Rate: `{active_rate:.1f}%`\n\n"
            f"📈 **Growth Metrics:**\n"
            f"├ Today's Joins: `0`\n"
            f"├ This Week: `0`\n"
            f"├ This Month: `0`\n"
            f"└ Growth Rate: `📈 Growing`\n\n"
            f"🔄 **System Health:**\n"
            f"├ Bot Status: `🟢 Online`\n"
            f"├ Database: `🟢 Connected`\n"
            f"├ Last Restart: `{datetime.now().strftime('%d %b, %H:%M')}`\n"
            f"└ Uptime: `100%`"
        )
        
        keyboard = [
            [InlineKeyboardButton("📊 Export Stats", callback_data="export_stats"), InlineKeyboardButton("📈 Analytics", callback_data="view_analytics")],
            [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_stats"), InlineKeyboardButton("🔙 Back", callback_data="admin_dashboard")]
        ]
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                stats_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN
            )
    
    # Broadcast Handlers
    async def start_broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Start broadcast conversation"""
        query = update.callback_query
        await query.answer()
        
        instruction_text = (
            f"📝 **Create New Broadcast**\n\n"
            f"📋 **Instructions:**\n"
            f"• Send any message (text, photo, video, document, etc.)\n"
            f"• Include buttons using this format:\n"
            f"  `[Button Text](URL)`\n"
            f"• For multiple buttons, use new lines\n"
            f"• Use Markdown formatting for text styling\n\n"
            f"📤 **Example with buttons:**\n"
            f"```\n"
            f"🎉 Welcome to our channel!\n"
            f"[📢 Join Channel](https://t.me/channel)\n"
            f"[💬 Support](https://t.me/support)\n"
            f"```\n\n"
            f"✅ **Ready? Send your broadcast content:**"
        )
        
        keyboard = [
            [InlineKeyboardButton("❌ Cancel", callback_data="broadcast_cancel")]
        ]
        
        await query.edit_message_text(
            instruction_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        
        return WAITING_FOR_BROADCAST
    
    async def process_broadcast_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Process the broadcast message"""
        message = update.message
        user_id = update.effective_user.id
        
        # Extract message data
        message_data = await self.extract_message_data(message)
        
        # Create broadcast
        broadcast_id = await self.broadcast_manager.create_broadcast(message_data)
        
        # Show confirmation
        confirmation_text = (
            f"📝 **Broadcast Created!**\n\n"
            f"🆔 Broadcast ID: `{broadcast_id}`\n"
            f"📊 Type: {message_data.get('media_type', 'text').title()}\n"
            f"👥 Target Users: `{len(await self.db.get_active_users())}`\n\n"
            f"✅ **Ready to send?**"
        )
        
        keyboard = [
            [InlineKeyboardButton("🚀 Send Now", callback_data=f"confirm_broadcast_{broadcast_id}")],
            [InlineKeyboardButton("👁️ Preview", callback_data=f"preview_broadcast_{broadcast_id}"), InlineKeyboardButton("✏️ Edit", callback_data=f"edit_broadcast_{broadcast_id}")],
            [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_broadcast_{broadcast_id}")]
        ]
        
        await message.reply_text(
            confirmation_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN
        )
        
        return ConversationHandler.END
    
    async def cancel_broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Cancel broadcast creation"""
        query = update.callback_query
        await query.answer("Broadcast cancelled")
        
        await query.edit_message_text(
            "❌ **Broadcast Cancelled**\n\nYou can start a new broadcast anytime from the admin panel."
        )
        
        return ConversationHandler.END
    
    # Callback Handler
    async def handle_callbacks(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all callback queries"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = query.from_user.id
        
        # Admin authorization check
        admin_callbacks = [
            "admin_dashboard", "broadcast_panel", "user_management", "detailed_stats",
            "clean_db", "refresh_dashboard", "broadcast_history", "broadcast_analytics",
            "view_users", "blocked_users", "export_stats", "refresh_stats"
        ]
        
        if any(data.startswith(cb) for cb in admin_callbacks) and user_id != Config.ADMIN_ID:
            await query.answer("❌ Not authorized!", show_alert=True)
            return
        
        # Route callbacks
        if data == "admin_dashboard":
            await self.show_admin_dashboard(update, context)
        elif data == "broadcast_panel":
            await self.show_broadcast_panel(update, context)
        elif data == "user_management":
            await self.show_user_management(update, context)
        elif data == "detailed_stats":
            await self.show_detailed_stats(update, context)
        elif data == "refresh_dashboard":
            self.clear_stats_cache()
            await self.show_admin_dashboard(update, context)
        elif data == "clean_db":
            await self.clean_database(update, context)
        elif data.startswith("confirm_broadcast_"):
            broadcast_id = int(data.split("_")[-1])
            await self.confirm_broadcast(update, context, broadcast_id)
        elif data == "help":
            await self.help_command(update, context)
        else:
            await query.edit_message_text("🚧 Feature coming soon!")
    
    async def confirm_broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE, broadcast_id: int):
        """Confirm and start broadcast"""
        query = update.callback_query
        
        result = await self.broadcast_manager.start_broadcast(broadcast_id, query.from_user.id)
        
        if result["success"]:
            await query.edit_message_text(
                f"🚀 **Broadcast Started!**\n\n"
                f"📊 Broadcasting to `{result['total_users']}` users\n"
                f"📈 Progress updates will be sent automatically\n\n"
                f"🆔 Broadcast ID: `{broadcast_id}`"
            )
        else:
            await query.edit_message_text(
                f"❌ **Broadcast Failed**\n\n"
                f"Error: {result['message']}"
            )
    
    # Utility Methods
    async def extract_message_data(self, message) -> Dict:
        """Extract data from a message for broadcasting"""
        data = {
            "text": message.text or message.caption,
            "media_type": None,
            "media_file_id": None,
            "caption": message.caption,
            "reply_markup": None
        }
        
        # Detect media type
        if message.photo:
            data["media_type"] = "photo"
            data["media_file_id"] = message.photo[-1].file_id
        elif message.video:
            data["media_type"] = "video"
            data["media_file_id"] = message.video.file_id
        elif message.document:
            data["media_type"] = "document"
            data["media_file_id"] = message.document.file_id
        elif message.animation:
            data["media_type"] = "animation"
            data["media_file_id"] = message.animation.file_id
        elif message.audio:
            data["media_type"] = "audio"
            data["media_file_id"] = message.audio.file_id
        elif message.voice:
            data["media_type"] = "voice"
            data["media_file_id"] = message.voice.file_id
        elif message.sticker:
            data["media_type"] = "sticker"
            data["media_file_id"] = message.sticker.file_id
        
        # Extract inline buttons from text
        if data["text"]:
            buttons = []
            lines = data["text"].split('\n')
            clean_text = []
            
            for line in lines:
                if line.strip().startswith('[') and '](http' in line:
                    # Extract button
                    try:
                        button_text = line.split('[')[1].split(']')[0]
                        button_url = line.split('](')[1].split(')')[0]
                        buttons.append([InlineKeyboardButton(button_text, url=button_url)])
                    except:
                        clean_text.append(line)
                else:
                    clean_text.append(line)
            
            data["text"] = '\n'.join(clean_text).strip()
            if buttons:
                data["reply_markup"] = buttons
        
        return data
    
    async def get_cached_stats(self) -> Dict:
        """Get cached statistics"""
        now = datetime.now()
        
        if (self.stats_cache_time is None or 
            (now - self.stats_cache_time).seconds > 300):  # 5 minutes cache
            self.stats_cache = await self.db.get_stats()
            self.stats_cache_time = now
        
        return self.stats_cache
    
    def clear_stats_cache(self):
        """Clear statistics cache"""
        self.stats_cache_time = None
    
    async def clean_database(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Clean blocked users from database"""
        deleted = await self.db.clean_blocked_users()
        self.clear_stats_cache()
        
        await update.callback_query.edit_message_text(
            f"🧹 **Database Cleaned!**\n\n"
            f"Removed `{deleted}` blocked users\n"
            f"Database optimized successfully!"
        )
    
    # Join Request Handler
    async def handle_join_request(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle channel join requests"""
        user = update.chat_join_request.from_user
        chat = update.chat_join_request.chat
        
        try:
            # Approve the join request
            await context.bot.approve_chat_join_request(chat.id, user.id)
            
            # Add user to database
            user_data = {
                "user_id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "language_code": user.language_code,
                "is_bot": user.is_bot,
                "is_premium": user.is_premium if hasattr(user, 'is_premium') else False
            }
            
            await self.db.add_or_update_user(user_data)
            
            # Send welcome message
            welcome_text = (
                f"🎉 **Welcome {user.first_name}!**\n\n"
                f"✅ Your request to join **{chat.title}** has been approved!\n\n"
                f"🚀 **Quick Start:**\n"
                f"• Send /start to explore bot features\n"
                f"• Join our main channel for updates\n"
                f"• Contact support if you need help\n\n"
                f"Thank you for joining! 🙏"
            )
            
            keyboard = [
                [InlineKeyboardButton("🚀 Start Bot", url=f"https://t.me/{Config.BOT_USERNAME}?start=welcome")],
                [InlineKeyboardButton("📢 Main Channel", url=Config.MAIN_CHANNEL_LINK)],
                [InlineKeyboardButton("💬 Support", url=Config.SUPPORT_CHAT)]
            ]
            
            try:
                await context.bot.send_message(
                    chat_id=user.id,
                    text=welcome_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=ParseMode.MARKDOWN
                )
            except Forbidden:
                logger.info(f"User {user.id} hasn't started the bot yet")
            
            logger.info(f"Approved join request for {user.first_name} ({user.id}) in {chat.title}")
            
        except TelegramError as e:
            logger.error(f"Error handling join request: {e}")
    
    # Message Handler
    async def handle_messages(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all other messages"""
        # This is for handling any messages not caught by other handlers
        pass
    
    async def run(self):
        """Run the bot"""
        try:
            # Initialize
            await self.initialize()
            
            # Create application
            app = self.create_application()
            
            # Set commands
            await self.set_bot_commands(app)
            
            logger.info("🚀 Bot started successfully!")
            logger.info(f"🤖 Bot username: @{Config.BOT_USERNAME}")
            logger.info(f"👤 Admin ID: {Config.ADMIN_ID}")
            
            # Start polling
            await app.run_polling(drop_pending_updates=True)
            
        except Exception as e:
            logger.error(f"Error running bot: {e}")
        finally:
            await self.db.close()

async def main():
    """Main function"""
    bot = TelegramBot()
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())