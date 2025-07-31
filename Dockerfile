# Use Python 3.11 slim image for smaller size
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire application
COPY . .

# Create data directory for database persistence
RUN mkdir -p /app/data

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Create non-root user for security with specific UID/GID
RUN groupadd --gid 1000 botuser && \
    useradd --create-home --shell /bin/bash --uid 1000 --gid botuser botuser && \
    chown -R botuser:botuser /app
USER botuser

# Expose port for web interface (if needed)
EXPOSE 8000

# Command to run the bot
CMD ["python", "bot.py"]