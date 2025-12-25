
from playwright.sync_api import sync_playwright

def verify_flashscore_esports():
    url = "https://www.flashscore.co.uk/esports/"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        print(f"Navigating to {url}...")
        page.goto(url, timeout=45000, wait_until='domcontentloaded')
        
        try:
            page.wait_for_selector(".event__match", timeout=15000)
        except:
            print("Timeout waiting for .event__match")
            
        matches = page.locator(".event__match").all()
        print(f"Found {len(matches)} matches on Flashscore Esports.")
        
        odds_count = 0
        for i, row in enumerate(matches):
            odds_els = row.locator(".odds__odd").all()
            if len(odds_els) > 0:
                odds_count += 1
                cols = [e.inner_text() for e in odds_els]
                print(f"Match {i} Odds: {cols}")
            else:
                if i < 3: print(f"Match {i} (No Odds)")
                
        print(f"Matches with odds: {odds_count}/{len(matches)}")
        browser.close()

if __name__ == "__main__":
    verify_flashscore_esports()
