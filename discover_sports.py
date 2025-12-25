
from playwright.sync_api import sync_playwright
import time

def check_sport(page, sport):
    url = f"https://www.aiscore.com/{sport}"
    try:
        page.goto(url, timeout=10000, wait_until='domcontentloaded')
        title = page.title()
        # Check if 404 or redirect to home
        url_now = page.url
        print(f"[{sport}] Title: {title} | URL: {url_now}")
        
        # Check for NUXT state to verify data
        data = page.evaluate("""() => {
            if (window.__NUXT__) return window.__NUXT__.state;
            return null;
        }""")
        
        if data:
            keys = list(data.keys())
            # Look for keys related to the sport
            relevant = [k for k in keys if sport.replace('-','') in k.lower()]
            print(f"  State keys ({len(keys)}): {relevant[:5]}...")
            return True
        else:
            print("  No NUXT state found.")
            return False

    except Exception as e:
        print(f"[{sport}] Error: {e}")
        return False

def explore_sports():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        candidates = [
            'motorsports', 'racing', 'f1', 'formula-1', 'auto-racing', # Motorsports attempts
            'volleyball', 'baseball', 'badminton', 'snooker', 'american-football', 'handball', 'water-polo', 'rugby'
        ]
        
        for s in candidates:
            check_sport(page, s)
            time.sleep(1)
            
        browser.close()

if __name__ == "__main__":
    explore_sports()
