#!/bin/bash

# Discord RPG Bot Docker Deployment Script
# This script helps manage the Discord bot container

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if .env file exists
check_env() {
    if [ ! -f .env ]; then
        print_warning "No .env file found. Creating template..."
        cat > .env << EOF
# Discord Bot Configuration
DISCORD_TOKEN=your_bot_token_here
COMMAND_PREFIX=!
ACTIVITY_NAME=Entropy
# ALLOWED_GUILD_ID=your_guild_id_here  # Optional: Set to restrict to single guild

# Database URL for PostgreSQL connection
DATABASE_URL=postgresql://thequietend_user:thequietend_pass@postgres:5432/thequietend_db
EOF
        print_warning "Run 'python setup.py' to populate the .env file with your bot token before starting."
        exit 1
    fi
}

# Create data directory if it doesn't exist
setup_directories() {
    print_status "Setting up directories..."
    mkdir -p data
    mkdir -p floormaps
    print_success "Directories created"
}

# Build the Docker image
build() {
    print_status "Building Docker image..."
    docker-compose build
    print_success "Docker image built successfully"
}

# Start the bot
start() {
    check_env
    setup_directories
    print_status "Starting Discord RPG Bot..."
    docker-compose up -d
    print_success "Bot started! Use 'docker-compose logs -f' to view logs"
}

# Stop the bot
stop() {
    print_status "Stopping Discord RPG Bot..."
    docker-compose down
    print_success "Bot stopped"
}

# Restart the bot
restart() {
    stop
    start
}

# View logs
logs() {
    docker-compose logs -f
}

# Show status
status() {
    docker-compose ps
}

# Update and restart
update() {
    print_status "Updating bot..."
    stop
    build
    start
    print_success "Bot updated and restarted"
}

# Backup database
backup() {
    print_status "Creating PostgreSQL database backup..."
    timestamp=$(date +%Y%m%d_%H%M%S)
    docker-compose exec postgres pg_dump -U thequietend_user thequietend_db > data/backup_${timestamp}.sql
    print_success "Database backed up to data/backup_${timestamp}.sql"
}

# Show help
show_help() {
    echo "Discord RPG Bot Docker Deployment Script"
    echo ""
    echo "Usage: ./deploy.sh [command]"
    echo ""
    echo "Commands:"
    echo "  build     - Build the Docker image"
    echo "  start     - Start the bot (creates .env template if needed)"
    echo "  stop      - Stop the bot"
    echo "  restart   - Restart the bot"
    echo "  logs      - View bot logs (follow mode)"
    echo "  status    - Show container status"
    echo "  update    - Stop, rebuild, and start the bot"
    echo "  backup    - Create database backup"
    echo "  help      - Show this help message"
    echo ""
}

# Main script logic
case "$1" in
    build)
        build
        ;;
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    logs)
        logs
        ;;
    status)
        status
        ;;
    update)
        update
        ;;
    backup)
        backup
        ;;
    help|--help|-h|"")
        show_help
        ;;
    *)
        print_error "Unknown command: $1"
        show_help
        exit 1
        ;;
esac