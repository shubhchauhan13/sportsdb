
from playwright.sync_api import sync_playwright
import json

def debug_network():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Use Mobile context as scraper does
        iphone = p.devices['iPhone 12']
        context = browser.new_context(**iphone)
        page = context.new_page()
        
        print("Starting network capture for AiScore Table Tennis...")
        
        def handle_response(response):
            try:
                # Filter for JSON
                if "application/json" in response.headers.get("content-type", ""):
                    url = response.url
                    # Ignore some common noise
                    if "google" in url or "tracking" in url: return
                    
                    print(f"XHR: {url} ({response.status})")
                    try:
                        data = response.json()
                        # Check for odds keywords deep in the JSON
                        s_data = json.dumps(data)
                        if "oddItems" in s_data:
                            print(f"!!! FOUND/ODDS in {url} !!!")
                            # print(s_data[:500])
                    except:
                        pass
            except:
                pass

        page.on("response", handle_response)
        
        page.goto("https://www.aiscore.com/table-tennis", wait_until="networkidle", timeout=30000)
        print("Page Loaded. Waiting 5s...")
        page.wait_for_timeout(5000)
        
        browser.close()

if __name__ == "__main__":
    debug_network()
