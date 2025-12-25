
from playwright.sync_api import sync_playwright

def verify_flashscore_specific():
    # Teams: Pipsqueak+4, Prestige, Weibo Gaming
    url = "https://www.flashscore.co.uk/esports/"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        print(f"Navigating to {url}...")
        page.goto(url, timeout=45000, wait_until='domcontentloaded')
        
        try:
            page.wait_for_selector(".event__match", timeout=15000)
        except: pass
        
        matches = page.locator(".event__match").all()
        print(f"Found {len(matches)} matches.")
        
        targets = ["Pipsqueak", "Prestige", "Weibo", "Bilibili"]
        
        for row in matches:
            text = row.inner_text()
            for t in targets:
                if t in text:
                    print(f"Found Match: {text}")
                    odds = row.locator(".odds__odd").all()
                    if odds:
                         print(f"  -> ODDS: {[o.inner_text() for o in odds]}")
                    else:
                         print("  -> NO ODDS")
                         
        browser.close()

if __name__ == "__main__":
    verify_flashscore_specific()
