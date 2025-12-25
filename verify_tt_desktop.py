
from playwright.sync_api import sync_playwright
import json

def check_desktop_tt():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Desktop UA
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        print("Navigating to AiScore Table Tennis (Desktop)...")
        page.goto("https://www.aiscore.com/table-tennis", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        
        data = page.evaluate("""() => {
            if (window.__NUXT__) return window.__NUXT__;
            return null;
        }""")
        
        if not data:
            print("No NUXT data found.")
            return
            
        state = data.get('state', {})
        tt_state = state.get('tabletennis', {})
        matches = tt_state.get('matches', [])
        
        print(f"Found {len(matches)} matches.")
        
        odds_count = 0
        for i, m in enumerate(matches[:10]):
            mid = m.get('id')
            ext = m.get('ext', {})
            has_odds = 'odds' in ext
            print(f"Match {mid}: Has Odds? {has_odds}")
            if has_odds:
                odds_count += 1
                # print(json.dumps(ext['odds'], indent=2))
        
        print(f"Total with odds (sample 10): {odds_count}")
        
        browser.close()

if __name__ == "__main__":
    check_desktop_tt()
