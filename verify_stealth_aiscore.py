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
        
        url = "https://www.aiscore.com/football"
        print(f"Navigating to {url} with stealth...")
        
        try:
            page.goto(url, timeout=60000)
            page.wait_for_timeout(5000)
            
            print(f"Title: {page.title()}")
            content = page.content()
            
            # Check for visible text again
            if "Shahdagh" in content or "Sabail" in content:
                 print("[SUCCESS] Found Shahdagh/Sabail!")
            else:
                 print("[FAIL] Specific match text NOT found.")
                 
            # Check NUXT
            data = page.evaluate("() => { if (window.__NUXT__) return window.__NUXT__; return null; }")
            if data:
                 print(f"NUXT Found. Keys: {list(data.keys())}")
                 state = data.get('state', {})
                 fb = state.get('football', {})
                 print(f"Football Keys: {list(fb.keys())}")
                 matches = fb.get('matchesData_matches', [])
                 print(f"matchesData_matches: {len(matches)}")
                 
                 hn = fb.get('home-new', {})
                 if 'matchesData' in hn:
                      print(f"home-new matchesData keys: {list(hn['matchesData'].keys())}")
            else:
                 print("NUXT NOT found")

        except Exception as e:
            print(f"Error: {e}")
            
        browser.close()

if __name__ == "__main__":
    verify_stealth_aiscore()
