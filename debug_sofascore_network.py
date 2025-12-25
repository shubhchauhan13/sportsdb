
from playwright.sync_api import sync_playwright
import json
import time

def debug_sofascore_api():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        print("Starting capture...")
        
        def handle(response):
            if "api/v1" in response.url and "json" in response.headers.get("content-type", ""):
                print(f"API: {response.url}")
                try:
                    data = response.json()
                    # Check for events list
                    if "events" in data:
                        events = data["events"]
                        print(f"  -> Found {len(events)} events!")
                        if len(events) > 0:
                            print(f"  -> Sample keys: {list(events[0].keys())}")
                except:
                    pass

        page.on("response", handle)
        
        page.goto("https://www.sofascore.com/table-tennis/live", wait_until="networkidle")
        print("Page loaded. Waiting 10s...")
        time.sleep(10)
        
        browser.close()

if __name__ == "__main__":
    debug_sofascore_api()
