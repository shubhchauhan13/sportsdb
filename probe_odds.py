import time
import json
from playwright.sync_api import sync_playwright

def probe():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Try fetching live football to see if odds are in the list
        url = "https://www.sofascore.com/api/v1/sport/football/events/live"
        print(f"Fetching {url}...")
        
        page.goto(url)
        text = page.inner_text("body")
        try:
            data = json.loads(text)
            events = data.get('events', [])
            if events:
                print(f"Found {len(events)} events.")
                # Print keys of the first event to check for 'odds'
                first_event = events[0]
                print("Event Keys:", first_event.keys())
                
                if 'odds' in first_event:
                    print("ODDS FOUND in List:", first_event['odds'])
                else:
                    print("No 'odds' key in list. Checking detailed event...")
                    # Try detail
                    e_id = first_event['id']
                    detail_url = f"https://www.sofascore.com/api/v1/event/{e_id}"
                    page.goto(detail_url)
                    d_text = page.inner_text("body")
                    d_data = json.loads(d_text)
                    event_detail = d_data.get('event', {})
                    print("Detail Keys:", event_detail.keys()) # Check here
                    
                    # Often odds are in a separate call: /api/v1/event/{id}/odds/1/all
                    odds_url = f"https://www.sofascore.com/api/v1/event/{e_id}/odds/1/all"
                    print(f"Checking Odds URL: {odds_url}")
                    resp = page.goto(odds_url)
                    if resp.status == 200:
                         o_text = page.inner_text("body")
                         print("ODDS API RESPONSE:", o_text[:500])
                    else:
                        print("ODDS API Failed:", resp.status)

            else:
                print("No live events found.")
        except Exception as e:
            print("Error:", e)
            
        browser.close()

if __name__ == "__main__":
    probe()
