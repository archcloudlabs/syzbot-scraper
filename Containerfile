# Use Python 3.11 slim as base image for smaller size
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py .

# Create output directory with appropriate permissions
RUN mkdir -p /app/output && \
    chmod 777 /app/output

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run as non-root user for security
RUN useradd -m appuser && \
    chown -R appuser:appuser /app
USER appuser

# Command to run the script
ENTRYPOINT ["python3", "app.py"]
# Default arguments (can be overridden)
CMD ["--release", "upstream"] 