
from playwright.sync_api import sync_playwright

def verify_fs():
    url = "https://www.flashscore.co.uk/table-tennis/"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        print(f"Navigating to {url}...")
        page.goto(url, timeout=45000, wait_until='domcontentloaded')
        
        try:
            page.wait_for_selector(".event__match", timeout=15000)
        except:
            print("Timeout waiting for .event__match")
            # Capture content to see if blocked
            # print(page.content()[:1000])
            
        matches = page.locator(".event__match").all()
        print(f"Found {len(matches)} matches on Flashscore.")
        
        odds_count = 0
        for i, row in enumerate(matches):
            # Check for odds. Flashscore usually uses .odds__odd
            odds_els = row.locator(".odds__odd").all()
            if len(odds_els) > 0:
                odds_count += 1
                cols = [e.inner_text() for e in odds_els]
                print(f"Match {i} Odds: {cols}")
            else:
                if i < 5: print(f"Match {i} text: {row.inner_text()} (No Odds)")
                
        print(f"Matches with odds: {odds_count}/{len(matches)}")
        browser.close()

if __name__ == "__main__":
    verify_fs()
