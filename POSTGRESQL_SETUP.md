# PostgreSQL Setup Guide for The Quiet End

This guide will help you set up PostgreSQL for The Quiet End bot, making it easily transferable to other systems.

> **Note:** PostgreSQL is the only supported database backend. Legacy SQLite helpers have been
> removed, and the PostgreSQL data directory (`pg_data/`) is created on demand and excluded from
> version control.

## ✅ **ISSUE RESOLVED**

The connection error `connection to server on socket "/tmp/.s.PGSQL.5432" failed` has been fixed with:

1. **Automatic SQL Conversion**: SQLite syntax (like `AUTOINCREMENT`) is automatically converted to PostgreSQL syntax (`SERIAL`)
2. **Robust Connection Handling**: Connection pool automatically recovers from connection issues
3. **Plug-and-Play Setup**: One-command setup for any system

## 🚀 Quick Setup (Recommended)

### Option 1: Automated Setup
```bash
# Make the script executable (if not already)
chmod +x start_postgres.sh

# Setup PostgreSQL and start the bot
./start_postgres.sh --bot
```

### Option 2: Setup Only (without starting bot)
```bash
./start_postgres.sh
```

## 📋 Manual Setup (if needed)

### 1. Prerequisites
Install PostgreSQL on your system:
```bash
# Ubuntu/Debian
sudo apt-get install postgresql postgresql-contrib

# CentOS/RHEL/Fedora
sudo dnf install postgresql postgresql-server

# macOS
brew install postgresql
```

### 2. Initialize and Start PostgreSQL
```bash
# Initialize database (if pg_data doesn't exist)
# The `pg_data/` directory is generated locally and remains untracked by Git.
initdb -D ./pg_data --auth-local=trust --auth-host=md5

# Start PostgreSQL server
pg_ctl start -D ./pg_data

# Check if running
pg_ctl status -D ./pg_data
```

### 3. Create Database and User
```bash
# Connect to PostgreSQL and create user/database
psql -h /tmp -d postgres -c "CREATE USER thequietend_user WITH PASSWORD 'thequietend_pass';"
psql -h /tmp -d postgres -c "CREATE DATABASE thequietend_db OWNER thequietend_user;"
psql -h /tmp -d postgres -c "GRANT ALL PRIVILEGES ON DATABASE thequietend_db TO thequietend_user;"
```

### 4. Test Connection
```bash
# Run the connection test
python test_connection.py
```

### 5. Start the Bot
```bash
python bot.py
```

## 🔧 Configuration Details

### Connection String
The bot uses this connection string by default:
```
postgresql://thequietend_user:thequietend_pass@localhost/thequietend_db?host=/tmp
```

### Environment Variable Override
You can override the connection string with:
```bash
export DATABASE_URL="postgresql://user:pass@host:port/dbname"
```

## 🔄 Managing PostgreSQL

### Start PostgreSQL
```bash
pg_ctl start -D ./pg_data
```

### Stop PostgreSQL
```bash
pg_ctl stop -D ./pg_data
```

### Check Status
```bash
pg_ctl status -D ./pg_data
```

## 📦 Transfer to Other Systems

To transfer this setup to another system:

1. **Create a backup** using `./deploy.sh backup` or `pg_dump -U thequietend_user thequietend_db > backup.sql`.
2. **Install PostgreSQL** on the new system and run `./start_postgres.sh` to provision the cluster.
3. **Restore your backup** with `psql` or `pg_restore`, then start the bot using `./start_postgres.sh --bot` if desired.

This workflow keeps environment-specific data out of source control while ensuring you can
reproduce the database quickly on a new host.

## 🐛 Troubleshooting

### Common Issues and Solutions

1. **"PostgreSQL is not installed"**
   - Install PostgreSQL using your system's package manager

2. **"Permission denied"**
   - Make sure the script is executable: `chmod +x start_postgres.sh`

3. **"Connection refused"**
   - PostgreSQL server is not running: `pg_ctl start -D ./pg_data`
   - Confirm the `pg_data/` directory exists locally (it should not be committed to Git).

4. **"Database does not exist"**
   - Run the setup script: `./start_postgres.sh`

### Connection Test
Always run the connection test to verify setup:
```bash
python test_connection.py
```

Expected output:
```
✅ Basic connection test passed
✅ Found X tables in database  
✅ SQL conversion test passed (AUTOINCREMENT → SERIAL)
🎉 All tests passed! PostgreSQL is ready for the bot.
```

## 💡 Features

- **Automatic SQL Conversion**: SQLite syntax automatically converted to PostgreSQL
- **Connection Pool**: Robust connection handling with automatic recovery
- **Plug-and-Play**: One command setup for any system
- **Portable**: Easy to transfer between systems
- **Self-Healing**: Automatically recovers from connection issues

## 📁 Key Files

- `start_postgres.sh` - Main setup script
- `test_connection.py` - Connection test utility
- `database.py` - Database abstraction layer with SQL conversion
- `pg_data/` - PostgreSQL data directory (created locally; excluded from Git)
- `POSTGRESQL_SETUP.md` - This documentation