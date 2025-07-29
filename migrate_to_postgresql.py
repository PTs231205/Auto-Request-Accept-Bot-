#!/usr/bin/env python3
"""
Migration script to move data from SQLite to PostgreSQL database
"""

import sqlite3
import asyncio
import logging
from datetime import datetime
from config import Config
from database import DatabaseManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseMigrator:
    def __init__(self, sqlite_file: str = "bot_users.db"):
        self.sqlite_file = sqlite_file
        self.postgres_db = DatabaseManager(Config.DATABASE_URL)
    
    async def migrate_data(self):
        """Migrate data from SQLite to PostgreSQL"""
        try:
            # Initialize PostgreSQL database
            await self.postgres_db.init_db()
            logger.info("PostgreSQL database initialized")
            
            # Check if SQLite database exists
            try:
                sqlite_conn = sqlite3.connect(self.sqlite_file)
                cursor = sqlite_conn.cursor()
                
                # Check if users table exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
                if not cursor.fetchone():
                    logger.warning("No users table found in SQLite database")
                    return
                
                # Get all users from SQLite
                cursor.execute("SELECT user_id, username, first_name, last_seen, is_blocked FROM users")
                sqlite_users = cursor.fetchall()
                
                logger.info(f"Found {len(sqlite_users)} users in SQLite database")
                
                # Migrate users to PostgreSQL
                migrated = 0
                for user_data in sqlite_users:
                    user_id, username, first_name, last_seen, is_blocked = user_data
                    
                    # Convert SQLite datetime string to Python datetime
                    try:
                        if last_seen:
                            last_seen_dt = datetime.fromisoformat(last_seen.replace('Z', '+00:00'))
                        else:
                            last_seen_dt = datetime.now()
                    except:
                        last_seen_dt = datetime.now()
                    
                    # Prepare user data for PostgreSQL
                    pg_user_data = {
                        "user_id": user_id,
                        "username": username,
                        "first_name": first_name,
                        "last_name": None,  # Not available in old SQLite schema
                        "language_code": None,  # Not available in old SQLite schema
                        "is_bot": False,  # Default value
                        "is_premium": False,  # Default value
                        "is_blocked": bool(is_blocked),
                        "is_admin": user_id == Config.ADMIN_ID,
                        "join_date": last_seen_dt,
                        "last_seen": last_seen_dt,
                        "failed_attempts": 0
                    }
                    
                    # Add user to PostgreSQL
                    await self.postgres_db.add_or_update_user(pg_user_data)
                    migrated += 1
                    
                    if migrated % 100 == 0:
                        logger.info(f"Migrated {migrated} users...")
                
                logger.info(f"Successfully migrated {migrated} users to PostgreSQL")
                
                # Close SQLite connection
                sqlite_conn.close()
                
                # Verify migration
                stats = await self.postgres_db.get_stats()
                logger.info(f"PostgreSQL database now has {stats['total']} total users")
                
                return True
                
            except sqlite3.Error as e:
                logger.error(f"SQLite error: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Migration error: {e}")
            return False
        finally:
            await self.postgres_db.close()
    
    async def backup_sqlite_data(self):
        """Create a backup of SQLite data before migration"""
        try:
            sqlite_conn = sqlite3.connect(self.sqlite_file)
            cursor = sqlite_conn.cursor()
            
            # Get all users
            cursor.execute("SELECT * FROM users")
            users = cursor.fetchall()
            
            # Save to backup file
            backup_file = f"sqlite_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(backup_file, 'w') as f:
                f.write("SQLite Database Backup\n")
                f.write(f"Date: {datetime.now()}\n")
                f.write("="*50 + "\n\n")
                
                f.write("Users:\n")
                for user in users:
                    f.write(f"{user}\n")
            
            logger.info(f"SQLite data backed up to {backup_file}")
            sqlite_conn.close()
            return backup_file
            
        except Exception as e:
            logger.error(f"Backup error: {e}")
            return None

async def main():
    """Main migration function"""
    logger.info("Starting database migration from SQLite to PostgreSQL")
    
    migrator = DatabaseMigrator()
    
    # Create backup first
    logger.info("Creating SQLite backup...")
    backup_file = await migrator.backup_sqlite_data()
    if backup_file:
        logger.info(f"Backup created: {backup_file}")
    
    # Perform migration
    logger.info("Starting migration...")
    success = await migrator.migrate_data()
    
    if success:
        logger.info("✅ Migration completed successfully!")
        logger.info("🔄 You can now start using the PostgreSQL database")
        logger.info("📁 SQLite backup is saved for safety")
    else:
        logger.error("❌ Migration failed!")
        logger.error("📁 Check the logs and try again")

if __name__ == "__main__":
    # Validate configuration before migration
    try:
        Config.validate()
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Configuration error: {e}")
        logger.error("Please check your .env file and database configuration")