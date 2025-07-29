import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    # Bot Configuration
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    ADMIN_ID = int(os.getenv("ADMIN_ID")) if os.getenv("ADMIN_ID") else None
    
    # Database Configuration
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://username:password@localhost/telegram_bot")
    
    # Channel Configuration
    MAIN_CHANNEL_LINK = os.getenv("MAIN_CHANNEL_LINK", "https://t.me/YOUR_CHANNEL")
    SUPPORT_CHAT = os.getenv("SUPPORT_CHAT", "https://t.me/YOUR_SUPPORT")
    
    # Bot Settings
    BOT_USERNAME = os.getenv("BOT_USERNAME", "Auto_request_bot")
    WELCOME_IMAGE = os.getenv("WELCOME_IMAGE")  # Optional welcome image URL
    
    # Broadcasting Settings
    BROADCAST_DELAY = float(os.getenv("BROADCAST_DELAY", "0.1"))  # Delay between messages
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
    RETRY_DELAY = float(os.getenv("RETRY_DELAY", "2"))
    
    # Features
    ENABLE_LOGS = os.getenv("ENABLE_LOGS", "true").lower() == "true"
    ENABLE_STATS = os.getenv("ENABLE_STATS", "true").lower() == "true"
    ENABLE_USER_INFO = os.getenv("ENABLE_USER_INFO", "true").lower() == "true"
    
    # Admin Panel
    ADMIN_PANEL_TITLE = os.getenv("ADMIN_PANEL_TITLE", "🔧 Admin Panel")
    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        if not cls.BOT_TOKEN:
            raise ValueError("BOT_TOKEN is required")
        if not cls.ADMIN_ID:
            raise ValueError("ADMIN_ID is required")
        if not cls.DATABASE_URL:
            raise ValueError("DATABASE_URL is required")
        return True