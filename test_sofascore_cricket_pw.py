from playwright.sync_api import sync_playwright
import json
import time

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1280, 'height': 720}
        )
        page = context.new_page()
        
        url = "https://www.sofascore.com/api/v1/sport/cricket/events/live"
        print(f"Navigating to {url} with Playwright...")
        
        # We navigate to the API URL directly. 
        # Usually browsers render the JSON as text.
        # This bypasses the simple 'requests' block because Playwright has proper TLS/Headers.
        try:
            response = page.goto(url, wait_until='networkidle')
            content = page.content()
            
            # Sofascore might return JSON inside <pre> tag or directly
            inner_text = page.inner_text('body')
            
            try:
                data = json.loads(inner_text)
                events = data.get('events', [])
                print(f"Success! Found {len(events)} live events.")
                if events:
                    print("Sample Event:")
                    print(json.dumps(events[0], indent=2))
            except:
                print("Could not parse JSON. Content preview:")
                print(content[:500])
                
        except Exception as e:
            print(f"Error: {e}")
            
        browser.close()

if __name__ == "__main__":
    run()
