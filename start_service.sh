#!/bin/bash

# Stop existing instance if running
pkill -f "scraper_service.py"

# Start in background with nohup
# > scraper_output.log sends output to file
# 2>&1 redirects errors to same file
# & puts it in background and detaches
nohup python3 scraper_service.py > scraper_output.log 2>&1 &

echo "Scraper started in background! PID: $!"
echo "Logs are being written to scraper_output.log"
echo "You can close the IDE now. The scraper will keep running."
