# 🤖 Advanced Telegram Auto Accept Bot

A powerful, feature-rich Telegram bot for automatically accepting channel join requests with advanced broadcasting capabilities and modern admin interface.

## ✨ Features

### 🔧 Core Features
- ✅ **Auto-approve channel join requests** - Instant approval without manual intervention
- 📢 **Advanced Broadcasting System** - Send messages to all users with retry mechanism
- 👥 **User Management** - Comprehensive user tracking and management
- 📊 **Detailed Analytics** - Real-time statistics and insights
- 🗃️ **PostgreSQL Database** - Robust, scalable database solution

### 🚀 Advanced Broadcasting
- 📱 **Multi-media Support** - Text, images, videos, documents, stickers, audio
- 🔘 **Inline Buttons** - Add custom buttons to broadcasts
- 🔄 **Auto-retry Failed Messages** - Attempts delivery 3 times before giving up
- 📊 **Real-time Progress Tracking** - Live updates during broadcast
- 📈 **Detailed Analytics** - Success rates and delivery statistics
- ⏱️ **Rate Limiting Protection** - Intelligent delay management

### 🎛️ Modern Admin Interface
- 🎨 **Clean, Intuitive UI** - Modern design inspired by top bots
- 📱 **Mobile-friendly** - Optimized for all devices
- ⚡ **Real-time Updates** - Live statistics and status updates
- 🔍 **Search & Filter** - Find users and broadcasts quickly
- 📊 **Visual Analytics** - Charts and graphs for data insights

### 🛠️ Technical Features
- 🔒 **Secure Authentication** - Admin-only access controls
- 📁 **Data Migration** - Easy migration from SQLite to PostgreSQL
- 🔄 **Auto-backup** - Automatic data backup during migration
- 📝 **Comprehensive Logging** - Detailed logs for debugging
- ⚙️ **Configurable Settings** - Extensive customization options

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- PostgreSQL database
- Telegram Bot Token (from @BotFather)
- Your Telegram User ID

### 📦 Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd telegram-auto-accept-bot
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up PostgreSQL database**
   ```bash
   # Create database
   createdb telegram_bot
   
   # Or using PostgreSQL CLI
   psql -c "CREATE DATABASE telegram_bot;"
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Run database migration (if upgrading from SQLite)**
   ```bash
   python migrate_to_postgresql.py
   ```

6. **Start the bot**
   ```bash
   python main.py
   ```

## ⚙️ Configuration

### Environment Variables

Create a `.env` file with the following variables:

```env
# Bot Configuration
BOT_TOKEN=your_bot_token_from_botfather
ADMIN_ID=your_telegram_user_id
BOT_USERNAME=your_bot_username

# Database
DATABASE_URL=postgresql://username:password@localhost:5432/telegram_bot

# Channels
MAIN_CHANNEL_LINK=https://t.me/your_channel
SUPPORT_CHAT=https://t.me/your_support

# Broadcasting Settings
BROADCAST_DELAY=0.1
MAX_RETRIES=3
RETRY_DELAY=2

# Features
ENABLE_LOGS=true
ENABLE_STATS=true
ENABLE_USER_INFO=true

# UI Customization
ADMIN_PANEL_TITLE=🔧 Admin Panel
```

### Database Setup

#### Local PostgreSQL
```bash
# Install PostgreSQL
sudo apt-get install postgresql postgresql-contrib

# Create user and database
sudo -u postgres psql
CREATE USER botuser WITH PASSWORD 'botpassword';
CREATE DATABASE telegram_bot OWNER botuser;
GRANT ALL PRIVILEGES ON DATABASE telegram_bot TO botuser;
```

#### Cloud Database (Example: Railway, Render, etc.)
```env
DATABASE_URL=postgresql://username:password@hostname:5432/database?sslmode=require
```

## 📱 Usage

### For Users
1. Start the bot with `/start`
2. Add the bot to your channel as admin
3. Give "Invite Users" permission
4. Users' join requests will be auto-approved

### For Admins
1. Use `/admin` to access admin panel
2. **Broadcasting**: Send messages to all users
3. **User Management**: View, search, and manage users
4. **Statistics**: Monitor bot performance
5. **Settings**: Configure bot behavior

## 📢 Broadcasting Guide

### Creating Broadcasts

1. Go to Admin Panel → Broadcast
2. Click "New Broadcast"
3. Send your content (text, media, etc.)
4. Add buttons using format: `[Button Text](URL)`
5. Preview and confirm

### Button Format Examples

```markdown
🎉 Welcome to our channel!

[📢 Join Channel](https://t.me/channel)
[💬 Support](https://t.me/support)
[🌐 Website](https://example.com)
```

### Supported Media Types
- 📝 Text messages
- 🖼️ Photos
- 🎥 Videos
- 📎 Documents
- 🎵 Audio files
- 🎤 Voice messages
- 😀 Stickers
- 🎬 Animations (GIFs)

## 🔧 Advanced Features

### User Management
- View all users with pagination
- Search users by ID, username, or name
- Block/unblock users
- Export user data
- Clean blocked users from database

### Broadcasting Analytics
- Real-time delivery status
- Success/failure rates
- Retry attempts tracking
- Time-based analytics
- Export broadcast reports

### Database Management
- Automatic backup before migration
- Data integrity checks
- Performance optimization
- Statistics caching

## 📊 Admin Commands

| Command | Description |
|---------|-------------|
| `/start` | Start the bot / Admin dashboard |
| `/admin` | Access admin panel |
| `/stats` | View detailed statistics |
| `/users` | User management panel |
| `/broadcast` | Broadcasting center |
| `/help` | Help and documentation |

## 🔧 Database Schema

### Users Table
- `user_id` - Telegram user ID (Primary Key)
- `username` - Telegram username
- `first_name` - User's first name
- `last_name` - User's last name
- `language_code` - User's language
- `is_bot` - Whether user is a bot
- `is_premium` - Premium status
- `is_blocked` - Block status
- `is_admin` - Admin status
- `join_date` - When user joined
- `last_seen` - Last activity
- `failed_attempts` - Failed delivery attempts

### Broadcast Messages Table
- `id` - Broadcast ID
- `message_text` - Message content
- `media_type` - Type of media
- `media_file_id` - Telegram file ID
- `caption` - Media caption
- `reply_markup` - Inline buttons (JSON)
- `sent_count` - Successfully sent
- `failed_count` - Failed deliveries
- `total_users` - Target audience size
- `status` - Broadcast status
- `created_at` - Creation time
- `completed_at` - Completion time

### Broadcast Logs Table
- `id` - Log ID
- `broadcast_id` - Related broadcast
- `user_id` - Target user
- `status` - Delivery status
- `attempt_count` - Retry attempts
- `error_message` - Error details
- `sent_at` - Delivery time

## 🚀 Deployment

### Docker Deployment
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
CMD ["python", "main.py"]
```

### Railway Deployment
1. Connect your GitHub repository
2. Add environment variables
3. Deploy automatically

### VPS Deployment
```bash
# Clone and setup
git clone <repo>
cd telegram-bot

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Setup systemd service
sudo cp telegram-bot.service /etc/systemd/system/
sudo systemctl enable telegram-bot
sudo systemctl start telegram-bot
```

## 🔒 Security

- ✅ Admin-only access controls
- ✅ Input validation and sanitization
- ✅ SQL injection protection
- ✅ Rate limiting
- ✅ Error handling
- ✅ Secure database connections
- ✅ Environment variable protection

## 📈 Performance

- ⚡ Asynchronous operations
- 🗄️ Database connection pooling
- 💾 Statistics caching
- 🔄 Efficient retry mechanisms
- 📊 Memory optimization
- ⏱️ Rate limit compliance

## 🐛 Troubleshooting

### Common Issues

1. **Database Connection Failed**
   ```bash
   # Check PostgreSQL is running
   sudo systemctl status postgresql
   
   # Verify connection string
   psql "postgresql://user:pass@host:5432/dbname"
   ```

2. **Bot Not Responding**
   ```bash
   # Check bot token
   curl https://api.telegram.org/bot<TOKEN>/getMe
   
   # Verify webhook settings
   curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo
   ```

3. **Migration Issues**
   ```bash
   # Check SQLite file exists
   ls -la bot_users.db
   
   # Run migration with debug
   python migrate_to_postgresql.py
   ```

### Debug Mode
Set `DEBUG=true` in `.env` for detailed logging.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License. See LICENSE file for details.

## 🙏 Acknowledgments

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) - Telegram Bot API wrapper
- [SQLAlchemy](https://sqlalchemy.org/) - Database ORM
- [PostgreSQL](https://postgresql.org/) - Database engine

## 📞 Support

- 💬 Telegram: [Support Chat](https://t.me/your_support)
- 📧 Email: support@example.com
- 📚 Documentation: [Wiki](https://github.com/repo/wiki)
- 🐛 Issues: [GitHub Issues](https://github.com/repo/issues)

---

**Made with ❤️ for the Telegram community**