
from playwright.sync_api import sync_playwright
import json
import time

def check_event(event_id):
    url = f"https://www.sofascore.com/api/v1/event/{event_id}"
    print(f"Fetching {url}...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        try:
            resp = page.goto(url)
            print(f"Status: {resp.status}")
            if resp.status == 200:
                text = page.inner_text("body")
                data = json.loads(text)
                event = data.get('event', {})
                # print(json.dumps(event, indent=2)) # Too noisy
                
                print("\n--- Key Fields ---")
                print(f"Status Desc: {event.get('status', {}).get('description')}")
                print(f"Status Type: {event.get('status', {}).get('type')}")
                print(f"Winner Code: {event.get('winnerCode')}")
                print(f"Home Score: {event.get('homeScore', {}).get('display')}")
                print(f"Away Score: {event.get('awayScore', {}).get('display')}")
                print(f"Note: {event.get('note')}") 
            else:
                print("Failed to load JSON.")
        except Exception as e:
            print(f"Error: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    check_event("14091052")
