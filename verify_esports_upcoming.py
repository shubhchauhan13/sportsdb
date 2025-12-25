
from playwright.sync_api import sync_playwright
import json

def verify_esports_upcoming():
    # Fetch scheduled for tomorrow to find a match with odds
    url = "https://www.sofascore.com/api/v1/sport/esports/scheduled-events/2025-12-26"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print(f"Fetching Upcoming: {url}")
        resp = page.goto(url)
        events = resp.json().get('events', [])
        print(f"Found {len(events)} upcoming events.")
        
        for ev in events:
            mid = ev.get('id')
            slug = ev.get('slug')
            if 'esl' in slug or 'blast' in slug or 'lck' in slug or 'lpl' in slug: # Major turnaments
                print(f"Checking potential major match: {slug} ({mid})")
                
                odds_url = f"https://www.sofascore.com/api/v1/event/{mid}/odds/1/all"
                o_resp = page.goto(odds_url)
                if o_resp.ok:
                    print(f"ODDS FOUND for {mid}!")
                    print(json.dumps(o_json.json(), indent=2)[:500])
                    break
                else:
                    print(f"No odds for {mid}")
                    
        browser.close()

if __name__ == "__main__":
    verify_esports_upcoming()
