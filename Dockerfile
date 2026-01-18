# Use the official Playwright image which includes all browser binaries
FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

WORKDIR /app

# Railway environment
ENV PYTHONUNBUFFERED=1
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Increase shared memory for Chromium (Railway fix)
ENV SHM_SIZE=256m
ENV DBUS_SESSION_BUS_ADDRESS=/dev/null


# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY scraper_service.py .

# Run the scraper (Railway handles health checks via /health endpoint)
CMD ["python", "-u", "scraper_service.py"]

