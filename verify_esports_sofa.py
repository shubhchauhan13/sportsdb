
from playwright.sync_api import sync_playwright
import json
import time

def verify_sofascore_esports():
    list_url = "https://www.sofascore.com/api/v1/sport/esports/events/live"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Use a high-quality, recent User Agent
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            extra_http_headers={
                'Accept': '*/*',
                'Referer': 'https://www.sofascore.com/',
                'Origin': 'https://www.sofascore.com'
            }
        )
        page = context.new_page()
        
        print(f"Fetching {list_url}...")
        try:
            resp = page.goto(list_url, timeout=30000, wait_until='domcontentloaded')
            if resp.ok:
                data = resp.json()
                events = data.get('events', [])
                print(f"Found {len(events)} Esports events.")
                
                if events:
                    ev = events[0]
                    mid = ev.get('id')
                    print(f"Sample ID: {mid}, Slug: {ev.get('slug')}")
                    
                    # Check odds for this sample
                    time.sleep(2) # Be polite
                    odds_url = f"https://www.sofascore.com/api/v1/event/{mid}/odds/1/all"
                    print(f"Checking odds: {odds_url}")
                    
                    o_resp = page.goto(odds_url)
                    if o_resp.ok:
                        o_data = o_resp.json()
                        markets = o_data.get('markets', [])
                        print(f"Markets found: {len(markets)}")
                        for m in markets[:3]:
                             print(f" - {m.get('marketName')}")
                    else:
                        print(f"Odds fetch failed: {o_resp.status}")
            else:
                print(f"List fetch failed: {resp.status}")
                
        except Exception as e:
            print(f"Error: {e}")
            
        browser.close()

if __name__ == "__main__":
    verify_sofascore_esports()
