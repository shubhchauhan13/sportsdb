
from playwright.sync_api import sync_playwright
import json
import time

def debug_esports_history():
    # Fetch recent finished matches 
    # Url: https://www.sofascore.com/api/v1/sport/esports/events/last/0
    # Or just generic list and filter
    
    # Let's try to get the list from the main page JSON if possible, or use the "scheduled" endpoint back in time? 
    # Sofascore API for past events: api/v1/sport/esports/scheduled-events/2025-12-24
    
    url = "https://www.sofascore.com/api/v1/sport/esports/scheduled-events/2025-12-25"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print(f"Fetching History: {url}")
        resp = page.goto(url)
        data = resp.json()
        events = data.get('events', [])
        print(f"Found {len(events)} events for today.")
        
        # Find one with status 'Finished' (code 100) and try to get odds
        target = None
        for ev in events:
            if ev.get('status', {}).get('code') == 100:
                target = ev
                break
        
        if target:
            mid = target.get('id')
            slug = target.get('slug')
            print(f"Testing Finished Match: {mid} ({slug})")
            
            # Try Odds Loop
            # Provider ID 1 is usually Bet365. Maybe Esports uses others?
            # Let's try checking the 'winning odds' provider via web interface simulation?
            # Or just hit the endpoint for providers first.
            
            prov_url = f"https://www.sofascore.com/api/v1/event/{mid}/odds/providers"
            print(f"Checking providers: {prov_url}")
            p_resp = page.goto(prov_url)
            if p_resp.ok:
                print("Providers:", p_resp.json())
            
            odds_url = f"https://www.sofascore.com/api/v1/event/{mid}/odds/1/all"
            print(f"Checking odds (Provider 1): {odds_url}")
            o_resp = page.goto(odds_url)
            if o_resp.ok:
                o_json = o_resp.json()
                print("Odds Data Found!")
                print(json.dumps(o_json, indent=2)[:500])
            else:
                print(f"Odds 404 for Provider 1")
                
        else:
            print("No finished matches found to test.")
        
        browser.close()

if __name__ == "__main__":
    debug_esports_history()
