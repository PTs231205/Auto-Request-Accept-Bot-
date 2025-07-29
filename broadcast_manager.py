import asyncio
import json
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from telegram import Bot, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.error import Forbidden, TelegramError, RetryAfter
from telegram.constants import ParseMode
from database import DatabaseManager, BroadcastMessage

logger = logging.getLogger(__name__)

class BroadcastManager:
    def __init__(self, bot: Bot, db_manager: DatabaseManager):
        self.bot = bot
        self.db = db_manager
        self.active_broadcasts = {}
        self.retry_delay = 2  # seconds between retries
        self.max_retries = 3
        
    async def create_broadcast(self, message_data: Dict) -> int:
        """Create a new broadcast message"""
        broadcast_data = {
            "message_text": message_data.get("text"),
            "media_type": message_data.get("media_type"),
            "media_file_id": message_data.get("media_file_id"),
            "caption": message_data.get("caption"),
            "reply_markup": json.dumps(message_data.get("reply_markup")) if message_data.get("reply_markup") else None,
            "status": "pending"
        }
        
        broadcast = await self.db.create_broadcast(broadcast_data)
        return broadcast.id
    
    async def start_broadcast(self, broadcast_id: int, admin_id: int) -> Dict:
        """Start broadcasting a message to all active users"""
        # Get active users
        users = await self.db.get_active_users()
        total_users = len(users)
        
        if total_users == 0:
            return {"success": False, "message": "No active users found"}
        
        # Update broadcast status
        await self.db.update_broadcast_status(broadcast_id, "in_progress")
        
        # Store broadcast info
        self.active_broadcasts[broadcast_id] = {
            "users": users,
            "current_index": 0,
            "sent_count": 0,
            "failed_count": 0,
            "admin_id": admin_id,
            "start_time": datetime.now()
        }
        
        # Start broadcasting in background
        asyncio.create_task(self._execute_broadcast(broadcast_id))
        
        return {
            "success": True, 
            "message": f"Broadcast started for {total_users} users",
            "broadcast_id": broadcast_id,
            "total_users": total_users
        }
    
    async def _execute_broadcast(self, broadcast_id: int):
        """Execute the actual broadcasting process"""
        try:
            # Get broadcast data from database
            async with self.db.async_session() as session:
                broadcast = await session.get(BroadcastMessage, broadcast_id)
                if not broadcast:
                    logger.error(f"Broadcast {broadcast_id} not found")
                    return
            
            broadcast_info = self.active_broadcasts[broadcast_id]
            users = broadcast_info["users"]
            
            for i, user_id in enumerate(users):
                broadcast_info["current_index"] = i
                
                success = await self._send_to_user(broadcast, user_id, broadcast_id)
                
                if success:
                    broadcast_info["sent_count"] += 1
                else:
                    broadcast_info["failed_count"] += 1
                
                # Add small delay to avoid flooding
                await asyncio.sleep(0.1)
                
                # Send progress update every 100 messages
                if (i + 1) % 100 == 0:
                    await self._send_progress_update(broadcast_id)
            
            # Complete broadcast
            await self._complete_broadcast(broadcast_id)
            
        except Exception as e:
            logger.error(f"Error in broadcast {broadcast_id}: {e}")
            await self.db.update_broadcast_status(broadcast_id, "failed")
        finally:
            # Clean up
            if broadcast_id in self.active_broadcasts:
                del self.active_broadcasts[broadcast_id]
    
    async def _send_to_user(self, broadcast: BroadcastMessage, user_id: int, 
                          broadcast_id: int, attempt: int = 1) -> bool:
        """Send message to a specific user with retry logic"""
        try:
            # Prepare message content
            reply_markup = None
            if broadcast.reply_markup:
                try:
                    reply_markup_data = json.loads(broadcast.reply_markup)
                    reply_markup = InlineKeyboardMarkup(reply_markup_data)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid reply markup for broadcast {broadcast_id}")
            
            # Send based on media type
            if broadcast.media_type == "photo":
                await self.bot.send_photo(
                    chat_id=user_id,
                    photo=broadcast.media_file_id,
                    caption=broadcast.caption or broadcast.message_text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN
                )
            elif broadcast.media_type == "video":
                await self.bot.send_video(
                    chat_id=user_id,
                    video=broadcast.media_file_id,
                    caption=broadcast.caption or broadcast.message_text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN
                )
            elif broadcast.media_type == "document":
                await self.bot.send_document(
                    chat_id=user_id,
                    document=broadcast.media_file_id,
                    caption=broadcast.caption or broadcast.message_text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN
                )
            elif broadcast.media_type == "animation":
                await self.bot.send_animation(
                    chat_id=user_id,
                    animation=broadcast.media_file_id,
                    caption=broadcast.caption or broadcast.message_text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN
                )
            elif broadcast.media_type == "audio":
                await self.bot.send_audio(
                    chat_id=user_id,
                    audio=broadcast.media_file_id,
                    caption=broadcast.caption or broadcast.message_text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN
                )
            elif broadcast.media_type == "voice":
                await self.bot.send_voice(
                    chat_id=user_id,
                    voice=broadcast.media_file_id,
                    caption=broadcast.caption or broadcast.message_text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN
                )
            elif broadcast.media_type == "sticker":
                await self.bot.send_sticker(
                    chat_id=user_id,
                    sticker=broadcast.media_file_id,
                    reply_markup=reply_markup
                )
                # Send text separately if exists
                if broadcast.message_text:
                    await self.bot.send_message(
                        chat_id=user_id,
                        text=broadcast.message_text,
                        reply_markup=reply_markup,
                        parse_mode=ParseMode.MARKDOWN
                    )
            else:
                # Plain text message
                await self.bot.send_message(
                    chat_id=user_id,
                    text=broadcast.message_text or "Test message",
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN
                )
            
            # Log success
            await self.db.log_broadcast_attempt(
                broadcast_id, user_id, "sent", attempt
            )
            return True
            
        except Forbidden:
            # User blocked the bot
            await self.db.block_user(user_id)
            await self.db.log_broadcast_attempt(
                broadcast_id, user_id, "blocked", attempt, "User blocked bot"
            )
            return False
            
        except RetryAfter as e:
            # Rate limited, wait and retry
            if attempt < self.max_retries:
                await asyncio.sleep(e.retry_after + 1)
                return await self._send_to_user(broadcast, user_id, broadcast_id, attempt + 1)
            else:
                await self.db.log_broadcast_attempt(
                    broadcast_id, user_id, "failed", attempt, f"Rate limited: {str(e)}"
                )
                return False
                
        except TelegramError as e:
            # Other telegram errors
            if attempt < self.max_retries:
                await asyncio.sleep(self.retry_delay * attempt)
                return await self._send_to_user(broadcast, user_id, broadcast_id, attempt + 1)
            else:
                await self.db.increment_failed_attempts(user_id)
                await self.db.log_broadcast_attempt(
                    broadcast_id, user_id, "failed", attempt, str(e)
                )
                return False
                
        except Exception as e:
            # Unexpected errors
            logger.error(f"Unexpected error sending to {user_id}: {e}")
            await self.db.log_broadcast_attempt(
                broadcast_id, user_id, "failed", attempt, str(e)
            )
            return False
    
    async def _send_progress_update(self, broadcast_id: int):
        """Send progress update to admin"""
        if broadcast_id not in self.active_broadcasts:
            return
            
        info = self.active_broadcasts[broadcast_id]
        admin_id = info["admin_id"]
        
        progress = (info["current_index"] + 1) / len(info["users"]) * 100
        
        try:
            await self.bot.send_message(
                chat_id=admin_id,
                text=f"📊 *Broadcast Progress*\n\n"
                     f"Progress: {progress:.1f}%\n"
                     f"Sent: {info['sent_count']}\n"
                     f"Failed: {info['failed_count']}\n"
                     f"Remaining: {len(info['users']) - info['current_index'] - 1}",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Failed to send progress update: {e}")
    
    async def _complete_broadcast(self, broadcast_id: int):
        """Complete the broadcast and send final report"""
        if broadcast_id not in self.active_broadcasts:
            return
            
        info = self.active_broadcasts[broadcast_id]
        admin_id = info["admin_id"]
        
        # Update database
        await self.db.update_broadcast_status(
            broadcast_id, "completed", info["sent_count"], info["failed_count"]
        )
        
        # Calculate time taken
        time_taken = datetime.now() - info["start_time"]
        
        # Send completion report
        try:
            await self.bot.send_message(
                chat_id=admin_id,
                text=f"✅ *Broadcast Completed!*\n\n"
                     f"📊 **Statistics:**\n"
                     f"• Total Users: {len(info['users'])}\n"
                     f"• Successfully Sent: {info['sent_count']}\n"
                     f"• Failed: {info['failed_count']}\n"
                     f"• Success Rate: {(info['sent_count']/len(info['users'])*100):.1f}%\n"
                     f"• Time Taken: {str(time_taken).split('.')[0]}\n\n"
                     f"🆔 Broadcast ID: `{broadcast_id}`",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Failed to send completion report: {e}")
    
    async def get_broadcast_status(self, broadcast_id: int) -> Optional[Dict]:
        """Get current status of a broadcast"""
        if broadcast_id in self.active_broadcasts:
            info = self.active_broadcasts[broadcast_id]
            return {
                "status": "in_progress",
                "progress": (info["current_index"] + 1) / len(info["users"]) * 100,
                "sent": info["sent_count"],
                "failed": info["failed_count"],
                "total": len(info["users"])
            }
        
        # Check database for completed broadcasts
        async with self.db.async_session() as session:
            broadcast = await session.get(BroadcastMessage, broadcast_id)
            if broadcast:
                return {
                    "status": broadcast.status,
                    "sent": broadcast.sent_count,
                    "failed": broadcast.failed_count,
                    "total": broadcast.total_users
                }
        
        return None
    
    async def cancel_broadcast(self, broadcast_id: int) -> bool:
        """Cancel an ongoing broadcast"""
        if broadcast_id in self.active_broadcasts:
            del self.active_broadcasts[broadcast_id]
            await self.db.update_broadcast_status(broadcast_id, "cancelled")
            return True
        return False
    
    async def retry_failed_messages(self, broadcast_id: int) -> Dict:
        """Retry sending to users who failed to receive the message"""
        failed_users = await self.db.get_failed_broadcast_users(broadcast_id)
        
        if not failed_users:
            return {"success": False, "message": "No failed users found for retry"}
        
        # Get broadcast data
        async with self.db.async_session() as session:
            broadcast = await session.get(BroadcastMessage, broadcast_id)
            if not broadcast:
                return {"success": False, "message": "Broadcast not found"}
        
        # Retry sending to failed users
        retry_sent = 0
        retry_failed = 0
        
        for user_id in failed_users:
            success = await self._send_to_user(broadcast, user_id, broadcast_id)
            if success:
                retry_sent += 1
            else:
                retry_failed += 1
        
        return {
            "success": True,
            "message": f"Retry completed: {retry_sent} sent, {retry_failed} failed",
            "retry_sent": retry_sent,
            "retry_failed": retry_failed
        }