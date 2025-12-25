
from playwright.sync_api import sync_playwright
import json

def verify_sofascore_odds():
    list_url = "https://www.sofascore.com/api/v1/sport/table-tennis/events/live"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            extra_http_headers={
                'Accept': 'application/json, text/plain, */*',
                'Referer': 'https://www.sofascore.com/',
            }
        )
        page = context.new_page()
        
        # 1. Get List
        print("Fetching List...")
        resp = page.goto(list_url)
        data = resp.json()
        events = data.get('events', [])
        
        if not events:
            print("No events found.")
            return

        target_id = events[0]['id']
        print(f"Target Match ID: {target_id} ({events[0].get('slug')})")
        
        # 2. Get Odds
        odds_url = f"https://www.sofascore.com/api/v1/event/{target_id}/odds/1/all"
        print(f"Fetching Odds: {odds_url}")
        resp = page.goto(odds_url)
        print(f"Status: {resp.status}")
        
        try:
            odds_data = resp.json()
            # print(json.dumps(odds_data, indent=2))
            

            markets = odds_data.get('markets', [])
            print(f"Total Markets: {len(markets)}")
            for m in markets:
                print(f"Market: {m.get('marketName')} (Main: {m.get('isMain')})")
                choices = m.get('choices', [])
                print(f"  Choices: {len(choices)}")
                for c in choices:
                     print(f"    {c.get('name')}: {c.get('fractionalValue')}")
                
        except Exception as e:
            print(f"Error parsing odds: {e}")

        browser.close()

if __name__ == "__main__":
    verify_sofascore_odds()
