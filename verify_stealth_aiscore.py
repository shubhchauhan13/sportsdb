from playwright.sync_api import sync_playwright

def verify_stealth_aiscore():
    with sync_playwright() as p:
        # Launch with arguments to hide automation
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
            ]
        )
        
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080}
        )
        
        # Stealth scripts
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        page = context.new_page()
        

        url = "https://www.aiscore.com/esports"
        print(f"Navigating to {url} with stealth...")
        
        try:
            page.goto(url, timeout=60000)
            page.wait_for_timeout(5000)
            
            print(f"Title: {page.title()}")
            content = page.content()
            
            # Check for NUXT
            data = page.evaluate("() => { if (window.__NUXT__) return window.__NUXT__; return null; }")
            if data:
                 print(f"NUXT Found.")
                 state = data.get('state', {})
                 # Esports usually in 'esports' key
                 es = state.get('esports', {})
                 print(f"Esports Keys: {list(es.keys())}")
                 matches = es.get('matches', []) or es.get('matchesData_matches', [])
                 print(f"Matches found: {len(matches)}")
                 
                 found_with_odds = 0
                 for m in matches[:5]:
                     print(f"ID: {m.get('id')} | Slug: {m.get('slug')} | Odds: {m.get('odds')}")
                     if m.get('odds'): found_with_odds += 1
                     
                 print(f"Sampled 5. Found with odds: {found_with_odds}")
            else:
                 print("NUXT NOT found")

        except Exception as e:
            print(f"Error: {e}")
            
        browser.close()

if __name__ == "__main__":
    verify_stealth_aiscore()
