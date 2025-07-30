# Docker Deployment Guide

This guide explains how to deploy the Discord RPG Bot using Docker on a VPS without pip access.

## Prerequisites

- Docker and Docker Compose installed on your VPS
- Discord bot token
- Discord server (guild) ID where the bot will operate

## Quick Start

1. **Clone/Upload the bot files to your VPS**

2. **Make the deployment script executable:**
   ```bash
   chmod +x deploy.sh
   ```

3. **Start the bot (this will create a .env template):**
   ```bash
   ./deploy.sh start
   ```

4. **Edit the .env file with your credentials:**
   ```bash
   nano .env
   ```
   
   Fill in your actual values:
   ```env
   DISCORD_TOKEN=your_actual_bot_token_here
   COMMAND_PREFIX=!
   ACTIVITY_NAME=Entropy
   ALLOWED_GUILD_ID=your_actual_guild_id_here
   ```

5. **Restart the bot to apply changes:**
   ```bash
   ./deploy.sh restart
   ```

## Available Commands

The `deploy.sh` script provides these commands:

- `./deploy.sh build` - Build the Docker image
- `./deploy.sh start` - Start the bot
- `./deploy.sh stop` - Stop the bot  
- `./deploy.sh restart` - Restart the bot
- `./deploy.sh logs` - View bot logs (follow mode)
- `./deploy.sh status` - Show container status
- `./deploy.sh update` - Stop, rebuild, and start the bot
- `./deploy.sh backup` - Create database backup
- `./deploy.sh help` - Show help message

## Manual Docker Commands

If you prefer to use Docker commands directly:

```bash
# Build the image
docker-compose build

# Start the bot
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the bot
docker-compose down

# Check status
docker-compose ps
```

## File Structure

After deployment, your directory should look like this:

```
├── bot.py                 # Main bot file
├── config.py             # Configuration (uses environment variables)
├── database.py           # Database wrapper
├── requirements.txt      # Python dependencies
├── Dockerfile           # Docker build instructions
├── docker-compose.yml   # Docker service configuration
├── .dockerignore        # Files to exclude from Docker build
├── deploy.sh            # Deployment script
├── .env                 # Environment variables (created on first run)
├── cogs/                # Bot command modules
├── utils/               # Utility modules
├── data/                # Database and persistent data (created on first run)
├── floormaps/           # Floor map files
└── landing/             # Web interface files
```

## Database Persistence

The bot's SQLite database is stored in the `./data/` directory on your host system and mounted into the container. This ensures your bot's data persists even when the container is recreated.

## Monitoring

- View live logs: `./deploy.sh logs`
- Check container health: `./deploy.sh status`
- The container includes a health check that verifies Discord.py is available

## Troubleshooting

### Bot won't start
1. Check if Docker is running: `docker --version`
2. Verify your .env file has correct values
3. Check logs: `./deploy.sh logs`

### Permission issues
Make sure the deploy script is executable:
```bash
chmod +x deploy.sh
```

### Database issues
- Create a backup before major changes: `./deploy.sh backup`
- Database files are in the `./data/` directory

### Memory issues
The container is limited to 512MB RAM by default. Adjust in `docker-compose.yml` if needed:
```yaml
deploy:
  resources:
    limits:
      memory: 1G  # Increase as needed
```

## Security Notes

- Bot token is stored in .env file (not in code)
- .env file is excluded from Docker build via .dockerignore
- Container runs as non-root user
- Sensitive files are excluded from the Docker image

## Updates

To update the bot with new code:
1. Upload new files to your VPS
2. Run: `./deploy.sh update`

This will stop the bot, rebuild the image with new code, and restart it.

## Support

If you encounter issues:
1. Check the logs: `./deploy.sh logs`
2. Verify your environment variables in .env
3. Ensure your bot token and guild ID are correct
4. Check Discord bot permissions in your server