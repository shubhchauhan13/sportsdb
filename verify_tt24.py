
from playwright.sync_api import sync_playwright

def verify_tt24():
    url = "https://www.tabletennis24.com/"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        print(f"Navigating to {url}...")
        page.goto(url, timeout=30000)
        
        try:
            page.wait_for_selector(".event__match", timeout=10000)
        except:
            print("Timeout waiting for .event__match")
            
        matches = page.locator(".event__match").all()
        print(f"Found {len(matches)} matches on TableTennis24.")
        
        odds_count = 0
        for i, row in enumerate(matches):
            text = row.inner_text()
            # print(f"Row {i}: {text}")
            
            # Check for odds elements (usually .odds__odd)
            odds_els = row.locator(".odds__odd").all()
            if len(odds_els) > 0:
                odds_count += 1
                o1 = odds_els[0].inner_text()
                o2 = odds_els[1].inner_text() if len(odds_els) > 1 else "?"
                print(f"Match {i} Odds: {o1} - {o2}")
            else:
                if i < 5: print(f"Match {i} has NO odds.")
                
        print(f"Matches with odds: {odds_count}/{len(matches)}")
        browser.close()

if __name__ == "__main__":
    verify_tt24()
