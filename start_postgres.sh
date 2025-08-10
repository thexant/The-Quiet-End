#!/bin/bash

# The Quiet End - PostgreSQL Startup Script
# This script makes the bot easily transferable to other systems

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PG_DATA_DIR="$PROJECT_DIR/pg_data"

echo "🎮 Starting The Quiet End PostgreSQL Setup"

# Function to check if PostgreSQL is installed
check_postgresql() {
    if ! command -v pg_ctl &> /dev/null; then
        echo "❌ PostgreSQL is not installed. Please install PostgreSQL first:"
        echo "   Ubuntu/Debian: sudo apt-get install postgresql postgresql-contrib"
        echo "   CentOS/RHEL:   sudo yum install postgresql postgresql-server"
        echo "   macOS:         brew install postgresql"
        exit 1
    fi
    echo "✅ PostgreSQL found"
}

# Function to initialize PostgreSQL if needed
init_postgresql() {
    if [ ! -d "$PG_DATA_DIR" ]; then
        echo "🔧 Initializing PostgreSQL database..."
        initdb -D "$PG_DATA_DIR" --auth-local=trust --auth-host=md5
        echo "✅ PostgreSQL initialized"
    else
        echo "✅ PostgreSQL data directory exists"
    fi
}

# Function to start PostgreSQL server
start_postgresql() {
    if pg_ctl status -D "$PG_DATA_DIR" &> /dev/null; then
        echo "✅ PostgreSQL server is already running"
    else
        echo "🚀 Starting PostgreSQL server..."
        pg_ctl start -D "$PG_DATA_DIR" -l "$PROJECT_DIR/logfile"
        sleep 2
        echo "✅ PostgreSQL server started"
    fi
}

# Function to create database and user if needed
setup_database() {
    echo "🔧 Setting up database and user..."
    
    # Create user if it doesn't exist
    psql -h /tmp -d postgres -c "CREATE USER thequietend_user WITH PASSWORD 'thequietend_pass';" 2>/dev/null || echo "User already exists"
    
    # Create database if it doesn't exist
    psql -h /tmp -d postgres -c "CREATE DATABASE thequietend_db OWNER thequietend_user;" 2>/dev/null || echo "Database already exists"
    
    # Grant privileges
    psql -h /tmp -d postgres -c "GRANT ALL PRIVILEGES ON DATABASE thequietend_db TO thequietend_user;" 2>/dev/null || true
    
    echo "✅ Database setup complete"
}

# Function to test connection
test_connection() {
    echo "🧪 Testing database connection..."
    if psql -h /tmp -U thequietend_user -d thequietend_db -c "SELECT 1;" &> /dev/null; then
        echo "✅ Database connection successful"
    else
        echo "❌ Database connection failed"
        exit 1
    fi
}

# Function to start the bot
start_bot() {
    echo "🎮 Starting The Quiet End bot..."
    cd "$PROJECT_DIR"
    python bot.py
}

# Function to stop PostgreSQL (for cleanup)
stop_postgresql() {
    echo "🛑 Stopping PostgreSQL server..."
    pg_ctl stop -D "$PG_DATA_DIR" -m fast
    echo "✅ PostgreSQL server stopped"
}

# Handle script interruption
cleanup() {
    echo ""
    echo "🔄 Cleaning up..."
    stop_postgresql 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM

# Main execution
main() {
    check_postgresql
    init_postgresql
    start_postgresql
    setup_database
    test_connection
    
    if [ "$1" = "--bot" ] || [ "$1" = "-b" ]; then
        start_bot
    else
        echo ""
        echo "✅ PostgreSQL setup complete!"
        echo "📝 Connection details:"
        echo "   Host: localhost (Unix socket: /tmp)"
        echo "   Database: thequietend_db"
        echo "   User: thequietend_user"
        echo ""
        echo "🎮 To start the bot, run: ./start_postgres.sh --bot"
        echo "🛑 To stop PostgreSQL, run: pg_ctl stop -D $PG_DATA_DIR"
    fi
}

# Show help
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "The Quiet End - PostgreSQL Startup Script"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --bot, -b     Start the bot after setting up PostgreSQL"
    echo "  --help, -h    Show this help message"
    echo ""
    echo "This script will:"
    echo "  1. Check if PostgreSQL is installed"
    echo "  2. Initialize PostgreSQL data directory if needed"
    echo "  3. Start PostgreSQL server"
    echo "  4. Create database and user if needed"
    echo "  5. Test the connection"
    echo "  6. Optionally start the bot"
    exit 0
fi

main "$@"