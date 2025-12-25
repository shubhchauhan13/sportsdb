
from playwright.sync_api import sync_playwright
import json

def debug_tt_providers():
    # ID from my previous check that matches a live game with missing odds
    # sf_15271045 (konstantinov-zaycev) might be finished, let's find a new live one
    
    list_url = "https://www.sofascore.com/api/v1/sport/table-tennis/events/live"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print("Fetching Live List...")
        resp = page.goto(list_url)
        events = resp.json().get('events', [])
        
        target_id = None
        for ev in events:
             # Find one, maybe?
             target_id = ev.get('id')
             print(f"Checking ID: {target_id}")
             
             # Check providers
             p_url = f"https://www.sofascore.com/api/v1/event/{target_id}/odds/providers"
             p_resp = page.goto(p_url)
             if p_resp.ok:
                 p_data = p_resp.json()
                 print(f"  Providers: {p_data}")
             else:
                 print("  No providers info.")
                 
             # Only check first 3
             if events.index(ev) > 2: break
             
        browser.close()

if __name__ == "__main__":
    debug_tt_providers()
