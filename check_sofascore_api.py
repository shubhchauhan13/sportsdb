from playwright.sync_api import sync_playwright
import json
import time

def check_api():
    url = "https://www.sofascore.com/api/v1/sport/mma/events/live"
    url_scheduled = "https://www.sofascore.com/api/v1/sport/mma/scheduled-events/2026-01-01"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print(f"Checking API: {url}")
        try:
            # Go to home first to set cookies/headers
            page.goto("https://www.sofascore.com", timeout=10000)
            
            response = page.goto(url, timeout=10000)
            print(f"Live API Status: {response.status}")
            if response.ok:
                try:
                    data = response.json()
                    print(f"Live Events: {len(data.get('events', []))}")
                except:
                    print("Could not parse JSON from Live API")

            response = page.goto(url_scheduled, timeout=10000)
            print(f"Scheduled API Status: {response.status}")
            if response.ok:
                try:
                    data = response.json()
                    events = data.get('events', [])
                    print(f"Scheduled Events: {len(events)}")
                    if events:
                        print(f"Sample Event: {json.dumps(events[0], indent=2)}")
                except:
                    print("Could not parse JSON from Scheduled API")

        except Exception as e:
            print(f"Error: {e}")
            
        browser.close()

if __name__ == "__main__":
    check_api()
