FROM python:3.11.13-slim-bullseye

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    ffmpeg \
    gcc \
    g++ \
    default-mysql-client \
    && rm -rf /var/lib/apt/lists/*

# Install yt-dlp
RUN curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /usr/local/bin/yt-dlp \
    && chmod a+rx /usr/local/bin/yt-dlp

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install -r requirements.txt

# Install python-dotenv for .env file support
RUN pip install python-dotenv

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /tmp/yt-downloads /app/logs

# Expose port
EXPOSE 5000

# Default command
CMD ["python", "download.py"]