import os
import asyncio
from datetime import datetime
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, DateTime, Boolean, Text, BigInteger
from sqlalchemy.sql import func
import logging

logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    language_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    is_bot: Mapped[bool] = mapped_column(Boolean, default=False)
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    join_date: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)

class BroadcastMessage(Base):
    __tablename__ = "broadcast_messages"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    media_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # photo, video, document, etc.
    media_file_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    caption: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reply_markup: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    total_users: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, in_progress, completed, failed

class BroadcastLog(Base):
    __tablename__ = "broadcast_logs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    broadcast_id: Mapped[int] = mapped_column(Integer)
    user_id: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(20))  # sent, failed, blocked
    attempt_count: Mapped[int] = mapped_column(Integer, default=1)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

class ChannelStats(Base):
    __tablename__ = "channel_stats"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(BigInteger)
    channel_name: Mapped[str] = mapped_column(String(200))
    total_requests: Mapped[int] = mapped_column(Integer, default=0)
    approved_requests: Mapped[int] = mapped_column(Integer, default=0)
    date: Mapped[datetime] = mapped_column(DateTime, default=func.now())

class DatabaseManager:
    def __init__(self, database_url: str):
        self.engine = create_async_engine(database_url, echo=False)
        self.async_session = async_sessionmaker(self.engine, expire_on_commit=False)
    
    async def init_db(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database initialized successfully")
    
    async def get_session(self) -> AsyncSession:
        return self.async_session()
    
    async def close(self):
        await self.engine.dispose()
    
    # User operations
    async def add_or_update_user(self, user_data: dict):
        async with self.async_session() as session:
            user = await session.get(User, user_data["user_id"])
            if user:
                # Update existing user
                for key, value in user_data.items():
                    if hasattr(user, key):
                        setattr(user, key, value)
                user.last_seen = datetime.now()
            else:
                # Create new user
                user = User(**user_data)
                session.add(user)
            
            await session.commit()
            return user
    
    async def get_user(self, user_id: int) -> Optional[User]:
        async with self.async_session() as session:
            return await session.get(User, user_id)
    
    async def get_active_users(self) -> List[int]:
        async with self.async_session() as session:
            result = await session.execute(
                "SELECT user_id FROM users WHERE is_blocked = false AND is_bot = false"
            )
            return [row[0] for row in result.fetchall()]
    
    async def block_user(self, user_id: int):
        async with self.async_session() as session:
            user = await session.get(User, user_id)
            if user:
                user.is_blocked = True
                await session.commit()
    
    async def unblock_user(self, user_id: int):
        async with self.async_session() as session:
            user = await session.get(User, user_id)
            if user:
                user.is_blocked = False
                user.failed_attempts = 0
                await session.commit()
    
    async def increment_failed_attempts(self, user_id: int):
        async with self.async_session() as session:
            user = await session.get(User, user_id)
            if user:
                user.failed_attempts += 1
                if user.failed_attempts >= 3:
                    user.is_blocked = True
                await session.commit()
    
    async def get_stats(self) -> dict:
        async with self.async_session() as session:
            total_result = await session.execute("SELECT COUNT(*) FROM users WHERE is_bot = false")
            total = total_result.scalar()
            
            active_result = await session.execute("SELECT COUNT(*) FROM users WHERE is_blocked = false AND is_bot = false")
            active = active_result.scalar()
            
            blocked = total - active
            
            premium_result = await session.execute("SELECT COUNT(*) FROM users WHERE is_premium = true AND is_bot = false")
            premium = premium_result.scalar()
            
            return {
                "total": total,
                "active": active,
                "blocked": blocked,
                "premium": premium
            }
    
    # Broadcast operations
    async def create_broadcast(self, broadcast_data: dict) -> BroadcastMessage:
        async with self.async_session() as session:
            broadcast = BroadcastMessage(**broadcast_data)
            session.add(broadcast)
            await session.commit()
            await session.refresh(broadcast)
            return broadcast
    
    async def update_broadcast_status(self, broadcast_id: int, status: str, sent_count: int = None, failed_count: int = None):
        async with self.async_session() as session:
            broadcast = await session.get(BroadcastMessage, broadcast_id)
            if broadcast:
                broadcast.status = status
                if sent_count is not None:
                    broadcast.sent_count = sent_count
                if failed_count is not None:
                    broadcast.failed_count = failed_count
                if status == "completed":
                    broadcast.completed_at = datetime.now()
                await session.commit()
    
    async def log_broadcast_attempt(self, broadcast_id: int, user_id: int, status: str, 
                                  attempt_count: int = 1, error_message: str = None):
        async with self.async_session() as session:
            log = BroadcastLog(
                broadcast_id=broadcast_id,
                user_id=user_id,
                status=status,
                attempt_count=attempt_count,
                error_message=error_message
            )
            session.add(log)
            await session.commit()
    
    async def get_failed_broadcast_users(self, broadcast_id: int) -> List[int]:
        async with self.async_session() as session:
            result = await session.execute(
                "SELECT user_id FROM broadcast_logs WHERE broadcast_id = ? AND status = 'failed' AND attempt_count < 3",
                (broadcast_id,)
            )
            return [row[0] for row in result.fetchall()]
    
    async def clean_blocked_users(self) -> int:
        async with self.async_session() as session:
            result = await session.execute("DELETE FROM users WHERE is_blocked = true")
            await session.commit()
            return result.rowcount