
from playwright.sync_api import sync_playwright
import json

def fetch_sofascore_direct():
    url = "https://www.sofascore.com/api/v1/sport/table-tennis/events/live"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            extra_http_headers={
                'Accept': 'application/json, text/plain, */*',
                'Referer': 'https://www.sofascore.com/',
                'Origin': 'https://www.sofascore.com'
            }
        )
        page = context.new_page()
        
        print(f"Fetching {url}...")
        response = page.goto(url, timeout=30000, wait_until="commit")
        
        print(f"Status: {response.status}")
        try:
            data = response.json()
            if 'events' in data:
                print(f"Found {len(data['events'])} events.")
                # Check for odds in first event works
                if len(data['events']) > 0:
                    ev = data['events'][0]
                    print("Keys:", list(ev.keys()))
                    # Usually odds are in 'odds' field which needs fetching? Or included?
                    # Sofascore list often does NOT include odds.
                    # We might need to fetch `api/v1/event/{id}/odds/1/all`
            else:
                print("No 'events' key in response.")
                print(json.dumps(data, indent=2)[:500])
        except Exception as e:
            print(f"Error parsing JSON: {e}")
            # print(response.text()[:200])

        browser.close()

if __name__ == "__main__":
    fetch_sofascore_direct()
