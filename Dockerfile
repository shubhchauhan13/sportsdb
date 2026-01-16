# Use the official Playwright image which includes all browser binaries
FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

WORKDIR /app

# Railway environment
ENV PYTHONUNBUFFERED=1
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY scraper_service.py .

# Health check for Railway monitoring (checks Flask /health endpoint)
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8080}/health || exit 1

# Run the scraper
CMD ["python", "-u", "scraper_service.py"]
