# SQLite to PostgreSQL Migration - Rollback Instructions

This document provides instructions for rolling back from PostgreSQL to SQLite if needed.

## Files Changed During Migration

### Core Files Modified:
1. `database.py` - Replaced with PostgreSQL version
2. `requirements.txt` - Updated dependencies
3. `config.py` - Updated database configuration
4. `docker-compose.yml` - Added PostgreSQL service
5. `deploy.sh` - Updated backup commands

### Backup Files Created:
- `database_sqlite_backup.py` - Original SQLite database class
- `database_sqlite_old.py` - Another backup of database.py
- `data/THEQUIETEND.db` - Original SQLite database (preserved)

## Rollback Procedure

### Step 1: Stop Current Services
```bash
# Stop the bot and PostgreSQL
docker compose down
# Or if running locally:
pg_ctl -D /home/vetaso/The-Quiet-End/pg_data stop
```

### Step 2: Restore SQLite Database Class
```bash
# Navigate to project directory
cd /home/vetaso/The-Quiet-End

# Restore the original SQLite database class
mv database.py database_postgresql.py
mv database_sqlite_backup.py database.py
```

### Step 3: Restore Requirements
```bash
# Edit requirements.txt to restore aiosqlite
sed -i 's/psycopg2-binary>=2.9.0/aiosqlite/' requirements.txt
```

### Step 4: Restore Configuration
```bash
# Edit config.py to restore SQLite configuration
# Replace this line in config.py:
# 'database_url': os.getenv('DATABASE_URL', 'postgresql://...'),
# With:
# 'db_path': os.getenv('DATABASE_PATH', 'data/THEQUIETEND.db'),
```

### Step 5: Restore Docker Configuration
```bash
# Remove PostgreSQL service from docker-compose.yml
# Remove the postgres service section and volumes section
# Change DATABASE_URL back to DATABASE_PATH in environment variables
```

### Step 6: Restore Deploy Script
```bash
# Edit deploy.sh to restore SQLite backup commands
# Replace PostgreSQL backup with SQLite backup
```

### Step 7: Test SQLite Connection
```bash
# Install SQLite dependencies
pip install aiosqlite

# Test the connection
python -c "from database import Database; db = Database(); print('✅ SQLite restored successfully')"
```

## Automated Rollback Script

Here's a script to automate the rollback process:

```bash
#!/bin/bash
# rollback_to_sqlite.sh

echo "🔄 Rolling back to SQLite..."

# Stop services
echo "Stopping services..."
docker compose down 2>/dev/null || true
pg_ctl -D ./pg_data stop 2>/dev/null || true

# Restore database class
echo "Restoring SQLite database class..."
mv database.py database_postgresql_backup.py
mv database_sqlite_backup.py database.py

# Restore requirements
echo "Restoring requirements.txt..."
sed -i 's/psycopg2-binary>=2.9.0/aiosqlite/' requirements.txt

# Install SQLite dependencies
echo "Installing SQLite dependencies..."
pip install aiosqlite

echo "✅ Rollback completed!"
echo "⚠️  Manual steps required:"
echo "   1. Edit config.py to restore DATABASE_CONFIG"
echo "   2. Edit docker-compose.yml to remove PostgreSQL service"
echo "   3. Edit deploy.sh to restore SQLite backup commands"
echo "   4. Test the bot functionality"
```

## Data Recovery

### If You Need to Recover Data from PostgreSQL:
```bash
# Export data from PostgreSQL
pg_dump -h /tmp -U thequietend_user thequietend_db > postgresql_backup.sql

# You can then use tools to convert PostgreSQL SQL to SQLite format if needed
```

### Verify SQLite Database Integrity:
```bash
sqlite3 data/THEQUIETEND.db "PRAGMA integrity_check;"
```

## Testing After Rollback

1. **Test Database Connection:**
   ```python
   from database import Database
   db = Database()
   result = db.execute_read_query("SELECT count(*) FROM characters", fetch='one')
   print(f"Characters: {result[0]}")
   ```

2. **Test Bot Startup:**
   ```bash
   python bot.py
   ```

3. **Test Core Commands:**
   - Character creation
   - Location travel
   - Economy functions

## Important Notes

- The original SQLite database (`data/THEQUIETEND.db`) was preserved during migration
- All data should be intact after rollback
- PostgreSQL foreign key constraint errors during migration were expected and don't affect rollback
- Always test thoroughly after rollback before going live

## Support

If you encounter issues during rollback:
1. Check that all backup files exist
2. Verify file permissions
3. Check Python module installations
4. Review error logs for specific issues

The migration can be re-attempted after successful rollback if needed.