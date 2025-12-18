from playwright.sync_api import sync_playwright

def verify_azscore():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        url = "https://www.azscore.com/live"
        print(f"Navigating to {url}...")
        
        try:
            page.goto(url, timeout=60000)
            page.wait_for_timeout(5000)
            
            print(f"Title: {page.title()}")
            
            # Check for match containers
            # Usually div "match-item" or similiar
            # Let's count divs with class containing 'game' or 'match'
            
            matches = page.locator('.game').count()
            print(f"'.game' elements found: {matches}")
            
            if matches == 0:
                matches = page.locator('.match').count()
                print(f"'.match' elements found: {matches}")

            # Try extracting text from first few
            if matches > 0:
                for i, item in enumerate(items):
                    txt = item.inner_text().replace('\n', ' | ')
                    print(f"Match {i}: {txt}")
            
        except Exception as e:
            print(f"Error: {e}")
            
        browser.close()

if __name__ == "__main__":
    verify_azscore()
