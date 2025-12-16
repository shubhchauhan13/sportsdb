

from playwright.sync_api import sync_playwright
import json
import time

def verify_sofascore():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # Try 1: www.sofascore.com (Seen in logs)
        url1 = "https://www.sofascore.com/api/v1/sport/cricket/events/live"
        print(f"[*] Trying Direct API Access: {url1}")
        
        try:
            response = page.goto(url1, timeout=30000)
            if response.status == 200:
                content = page.content()
                # Content will be wrapped in <html><body><pre>... or just text
                text = page.inner_text("body")

                try:
                    data = json.loads(text)
                    events = data.get('events', [])
                    print(f"[SUCCESS] Retrieved {len(events)} live matches from WWW.")
                    if events:
                        m = events[0]
                        print("Sample Match Data:")
                        print(f"Status Description: {m.get('status', {}).get('description')}")
                        print(f"Last Period: {m.get('lastPeriod')}")
                        print(f"Periods: {json.dumps(m.get('periods', {}), indent=2)}")
                        print(f"Home Score: {m.get('homeScore', {}).get('display')}")
                        print(f"Away Score: {m.get('awayScore', {}).get('display')}")
                    return
                except:
                    print(f"[WARN] Failed to parse JSON from WWW: {text[:100]}")
            else:
                print(f"[FAIL] WWW gave status {response.status}")
                
        except Exception as e:
            print(f"[ERROR] WWW failed: {e}")

        # Try 2: api.sofascore.com (User suggestion)
        url2 = "https://api.sofascore.com/api/v1/sport/cricket/events/live"
        print(f"[*] Trying API Domain: {url2}")
        
        try:
            response = page.goto(url2, timeout=30000)
            if response.status == 200:
                text = page.inner_text("body")
                data = json.loads(text)
                events = data.get('events', [])
                print(f"[SUCCESS] Retrieved {len(events)} live matches from API domain.")
                if events:
                    print(json.dumps(events[0], indent=2))
            else:
                print(f"[FAIL] API domain gave status {response.status}")
                
        except Exception as e:
            print(f"[ERROR] API domain failed: {e}")
            
        browser.close()

if __name__ == "__main__":
    verify_sofascore()


