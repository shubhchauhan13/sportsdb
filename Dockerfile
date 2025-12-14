# Use the official Playwright image which includes all browser binaries
# This saves us from installing huge dependencies manually
FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY scraper_service.py .

# Run the scraper
CMD ["python", "scraper_service.py"]
