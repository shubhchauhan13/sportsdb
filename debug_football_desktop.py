from playwright.sync_api import sync_playwright

def inspect_page(page, label):
    print(f"\n--- Inspecting {label} ---")
    try:
        page.goto('https://www.aiscore.com/football', timeout=60000)
        page.wait_for_timeout(5000)
        
        # Check Visible Text
        content = page.content()
        print(f"Page Title: {page.title()}")
        if "Shahdagh" in content or "Sabail" in content:
            print("[SUCCESS] Found 'Shahdagh' or 'Sabail' in page content!")
            # Try to locate the element
            rows = page.get_by_text("Shahdagh").count()
            print(f"Elements with 'Shahdagh': {rows}")
        else:
            print("[FAIL] Specific match text NOT found in DOM.")
            
        data = page.evaluate("() => { if (window.__NUXT__) return window.__NUXT__; return null; }")
        if data:
            state = data.get('state', {})
            # Check football key
            sport_state = state.get('football', {})
            print(f"Football keys: {list(sport_state.keys())}")
            
            matches = sport_state.get('matchesData_matches', [])
            print(f"matchesData_matches count: {len(matches)}")
            
            # Check home-new
            home_new = sport_state.get('home-new', {})
            if 'matchesData' in home_new:
                 m_data = home_new['matchesData']
                 print(f"matchesData type: {type(m_data)}")
                 
                 if isinstance(m_data, dict):
                     print(f"matchesData keys: {list(m_data.keys())}")
                     if 'matches' in m_data:
                         print(f"matches count: {len(m_data['matches'])}")
                     
                     if 'liveMatches' in m_data:
                         lm = m_data['liveMatches']
                         print(f"liveMatches count: {len(lm)}")
                         if lm: print(f"First Live Match: {lm[0]}")

                     if 'allMatches' in m_data:
                         am = m_data['allMatches']
                         print(f"allMatches count: {len(am)}")
                         
                     if 'competitions' in m_data:
                         print(f"competitions count: {len(m_data['competitions'])}")
                 
                 elif isinstance(m_data, list):
                     print(f"matchesData list len: {len(m_data)}")

        else:
            print("__NUXT__ not found")
            
    except Exception as e:
        print(f"Error: {e}")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    # Desktop Context
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    page = context.new_page()
    inspect_page(page, "Desktop /football/live")
    browser.close()
