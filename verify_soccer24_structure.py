from playwright.sync_api import sync_playwright

def verify_soccer24_structure():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled']
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = context.new_page()
        
        url = "https://www.soccer24.com/"
        print(f"Navigating to {url}...")
        
        try:
            page.goto(url, timeout=30000, wait_until='domcontentloaded')
            page.wait_for_selector('.event__match', timeout=10000)
            
            matches = page.locator('.event__match').all()
            print(f"Matches found: {len(matches)}")
            
            if matches:
                # Dump structure of first match
                m = matches[0]
                print(f"First Match Inner Text: {m.inner_text()}")
                print(f"First Match HTML: {m.inner_html()}")
                
                # Check specifics
                home = m.locator('.event__participant--home').inner_text()
                away = m.locator('.event__participant--away').inner_text()
                score_home = m.locator('.event__score--home').inner_text()
                score_away = m.locator('.event__score--away').inner_text()
                print(f"Parsed: {home} {score_home}-{score_away} {away}")
                
        except Exception as e:
            print(f"Error: {e}")
            
        browser.close()

if __name__ == "__main__":
    verify_soccer24_structure()
