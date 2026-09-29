FROM python:3.11-slim

WORKDIR /app

# Install system dependencies if required
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PORT=5050 \
    HOST=0.0.0.0

EXPOSE 5050

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5050/healthz || exit 1

CMD ["gunicorn", "--workers", "1", "--threads", "8", "--bind", "0.0.0.0:5050", "--timeout", "120", "app:app"]
