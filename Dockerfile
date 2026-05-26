# ASTRA Cloud Server Dockerfile
# For Oracle Cloud / any container runtime

FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV ASTRA_DATA_DIR=/data/astra
ENV PORT=5000

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    portaudio19-dev \
    tesseract-ocr \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements first (for Docker cache)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir flask flask-cors gunicorn

# Copy application code
COPY . .

# Create data directory
RUN mkdir -p /data/astra/users /data/astra/models /data/astra/training

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Run the cloud API server
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout", "120", "cloud.api_server:app"]
