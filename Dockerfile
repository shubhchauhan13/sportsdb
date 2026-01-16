# Use the official Playwright image which includes all browser binaries
FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

WORKDIR /app

# Railway environment
ENV PYTHONUNBUFFERED=1
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Install curl for healthcheck + cleanup to reduce image size
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY scraper_service.py .

# Health check for Railway monitoring
# Extended start period to allow browsers to initialize
HEALTHCHECK --interval=60s --timeout=30s --start-period=180s --retries=5 \
    CMD curl -f http://localhost:${PORT:-8080}/health || exit 1

# Run the scraper
CMD ["python", "-u", "scraper_service.py"]
