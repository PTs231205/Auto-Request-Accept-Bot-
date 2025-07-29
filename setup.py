#!/usr/bin/env python3
"""
Quick setup script for Advanced Telegram Auto Accept Bot
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def run_command(command, check=True):
    """Run a system command"""
    print(f"Running: {command}")
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Error: {result.stderr}")
        sys.exit(1)
    return result

def check_python_version():
    """Check if Python version is 3.8+"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ is required")
        sys.exit(1)
    print("✅ Python version check passed")

def check_postgresql():
    """Check if PostgreSQL is available"""
    result = run_command("psql --version", check=False)
    if result.returncode != 0:
        print("❌ PostgreSQL not found. Please install PostgreSQL first.")
        print("   Ubuntu/Debian: sudo apt-get install postgresql postgresql-contrib")
        print("   CentOS/RHEL: sudo yum install postgresql postgresql-server")
        print("   macOS: brew install postgresql")
        sys.exit(1)
    print("✅ PostgreSQL found")

def install_dependencies():
    """Install Python dependencies"""
    print("📦 Installing Python dependencies...")
    run_command("pip install -r requirements.txt")
    print("✅ Dependencies installed")

def setup_database():
    """Setup PostgreSQL database"""
    print("🗃️ Setting up database...")
    
    db_name = input("Enter database name (default: telegram_bot): ").strip() or "telegram_bot"
    db_user = input("Enter database user (default: botuser): ").strip() or "botuser"
    db_pass = input("Enter database password: ").strip()
    
    if not db_pass:
        print("❌ Database password is required")
        sys.exit(1)
    
    # Create user and database
    commands = [
        f"sudo -u postgres createuser {db_user}",
        f"sudo -u postgres createdb {db_name}",
        f"sudo -u postgres psql -c \"ALTER USER {db_user} WITH PASSWORD '{db_pass}';\"",
        f"sudo -u postgres psql -c \"GRANT ALL PRIVILEGES ON DATABASE {db_name} TO {db_user};\""
    ]
    
    for cmd in commands:
        result = run_command(cmd, check=False)
        if result.returncode != 0 and "already exists" not in result.stderr:
            print(f"Warning: {result.stderr}")
    
    return f"postgresql://{db_user}:{db_pass}@localhost:5432/{db_name}"

def setup_environment():
    """Setup environment variables"""
    print("⚙️ Setting up environment...")
    
    if os.path.exists(".env"):
        overwrite = input(".env file already exists. Overwrite? (y/N): ").strip().lower()
        if overwrite != 'y':
            print("Using existing .env file")
            return
    
    # Copy example file
    shutil.copy(".env.example", ".env")
    
    # Get configuration from user
    bot_token = input("Enter your Bot Token (from @BotFather): ").strip()
    admin_id = input("Enter your Telegram User ID: ").strip()
    bot_username = input("Enter your bot username (without @): ").strip()
    
    if not all([bot_token, admin_id, bot_username]):
        print("❌ All fields are required")
        sys.exit(1)
    
    # Setup database
    database_url = setup_database()
    
    # Update .env file
    env_content = f"""# Telegram Bot Configuration
BOT_TOKEN={bot_token}
ADMIN_ID={admin_id}
BOT_USERNAME={bot_username}

# Database Configuration
DATABASE_URL={database_url}

# Channel & Support Configuration
MAIN_CHANNEL_LINK=https://t.me/YOUR_CHANNEL
SUPPORT_CHAT=https://t.me/YOUR_SUPPORT

# Broadcasting Settings
BROADCAST_DELAY=0.1
MAX_RETRIES=3
RETRY_DELAY=2

# Bot Features
ENABLE_LOGS=true
ENABLE_STATS=true
ENABLE_USER_INFO=true

# Admin Panel
ADMIN_PANEL_TITLE=🔧 Admin Panel

# Development Settings
ENVIRONMENT=production
DEBUG=false
"""
    
    with open(".env", "w") as f:
        f.write(env_content)
    
    print("✅ Environment configured")

def setup_systemd_service():
    """Setup systemd service (optional)"""
    setup_service = input("Setup systemd service for auto-start? (Y/n): ").strip().lower()
    if setup_service == 'n':
        return
    
    current_dir = os.getcwd()
    user = os.getenv("USER", "botuser")
    
    # Update service file with current paths
    service_content = f"""[Unit]
Description=Advanced Telegram Auto Accept Bot
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User={user}
Group={user}
WorkingDirectory={current_dir}
ExecStart={sys.executable} {current_dir}/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
    
    # Write service file
    service_file = f"{current_dir}/telegram-bot.service"
    with open(service_file, "w") as f:
        f.write(service_content)
    
    print(f"📝 Service file created: {service_file}")
    print("To install the service, run:")
    print(f"sudo cp {service_file} /etc/systemd/system/")
    print("sudo systemctl enable telegram-bot")
    print("sudo systemctl start telegram-bot")

def migrate_sqlite_data():
    """Migrate data from SQLite if exists"""
    if os.path.exists("bot_users.db"):
        migrate = input("SQLite database found. Migrate data to PostgreSQL? (Y/n): ").strip().lower()
        if migrate != 'n':
            print("🔄 Migrating data...")
            run_command("python migrate_to_postgresql.py")
            print("✅ Data migration completed")

def main():
    """Main setup function"""
    print("🚀 Advanced Telegram Auto Accept Bot Setup")
    print("=" * 50)
    
    # Pre-checks
    check_python_version()
    check_postgresql()
    
    # Setup steps
    install_dependencies()
    setup_environment()
    migrate_sqlite_data()
    setup_systemd_service()
    
    print("\n" + "=" * 50)
    print("✅ Setup completed successfully!")
    print("\n📋 Next steps:")
    print("1. Edit .env file if needed")
    print("2. Run: python main.py")
    print("3. Add bot to your channel as admin")
    print("4. Give 'Invite Users' permission")
    print("\n📚 Documentation: README.md")
    print("🆘 Support: Check README.md for support links")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n❌ Setup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        sys.exit(1)