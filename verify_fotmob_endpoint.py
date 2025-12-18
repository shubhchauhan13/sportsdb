from playwright.sync_api import sync_playwright
import json

def verify_fotmob_endpoint():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Correct URL from network logs
        # Date format: YYYYMMDD. System is 2025-12-18
        url = "https://www.fotmob.com/api/data/matches?date=20251218&timezone=Asia/Kolkata&ccode3=IND"
        print(f"[*] Navigating to: {url}")
        
        try:
            # Use specific headers potentially mimicking the browser
            response = page.goto(url, timeout=30000)
            status = response.status
            print(f"[*] Status: {status}")
            
            if status == 200:
                try:
                    data = response.json()
                    print("[SUCCESS] JSON Decoded")
                    leagues = data.get('leagues', [])
                    print(f"[*] Leagues: {len(leagues)}")
                    
                    if leagues:
                        first_match = leagues[0]['matches'][0]
                        print(f"[*] Match: {first_match.get('home', {}).get('name')} vs {first_match.get('away', {}).get('name')}")
                        # Check keys for Odds
                        print(f"[*] Match Keys: {list(first_match.keys())}")
                except Exception as e:
                    print(f"[ERROR] JSON Parse: {e}")
                    print(f"[*] Body Sample: {response.body()[:500]}")
            else:
                print(f"[FAIL] Body: {response.body()[:500]}")
                
        except Exception as e:
            print(f"[ERROR] Request: {e}")
            
        browser.close()

if __name__ == "__main__":
    verify_fotmob_endpoint()
