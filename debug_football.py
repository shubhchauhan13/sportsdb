from playwright.sync_api import sync_playwright
import json

def inspect_page(page, label):
    print(f"\n--- Inspecting {label} ---")
    try:
        # Check __NUXT__
        data = page.evaluate("() => window.__NUXT__")
        if data:
            state = data.get('state', {})
            print(f"State keys: {list(state.keys())}")
            
            # Check football key
            football = state.get('football', {})
            print(f"Football keys: {list(football.keys())}")
            
            # Check for matches in common locations
            matches = football.get('matchesData_matches', [])
            print(f"matchesData_matches count: {len(matches)}")
            
            matches_alt = football.get('matches', [])
            print(f"matches count: {len(matches_alt)}")
            
            # Check home-new if exists
            home_new = football.get('home-new', {})
            if home_new:
                 print(f"home-new keys: {list(home_new.keys())}")
                 # Check deeper
                 if 'matchesData' in home_new:
                     m_data = home_new['matchesData']
                     print(f"matchesData type: {type(m_data)}")
                     if isinstance(m_data, dict):
                         print(f"matchesData keys (Comps): {list(m_data.keys())[:5]}")
                         # Check first comp values
                         for k, v in list(m_data.items())[:1]:
                             print(f"Comp {k} type: {type(v)}")
                             if isinstance(v, dict):
                                 # It seems to be a dict of matches? or dict with 'matches'?
                                 print(f"Comp {k} keys: {list(v.keys())}")
                                 if 'matches' in v:
                                     print(f"Matches in Comp {k}: {len(v['matches'])}")
                         
                         # Check competitions list
                         if 'competitions' in m_data:
                             comps = m_data['competitions']
                             print(f"Competitions list len: {len(comps)}")
                             if comps:
                                 print(f"First Comp Keys: {list(comps[0].keys())}")
            
            # Check today-matches
            today = state.get('today-matches', {})
            print(f"today-matches keys: {list(today.keys())}")
            if 'matchesData' in today:
                 tm_data = today['matchesData']
                 if isinstance(tm_data, dict) and 'matches' in tm_data:
                      print(f"today-matches matches count: {len(tm_data['matches'])}")
        else:
            print("__NUXT__ is None")
            
    except Exception as e:
        print(f"Error: {e}")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    
    # 1. Mobile - /football
    print("Launching Mobile Context...")
    iphone = p.devices['iPhone 12']
    context_mobile = browser.new_context(**iphone)
    page_mobile = context_mobile.new_page()
    try:
        page_mobile.goto('https://www.aiscore.com/football', timeout=30000)
        page_mobile.wait_for_timeout(3000)
        inspect_page(page_mobile, "Mobile /football")
    except Exception as e:
        print(f"Mobile failed: {e}")

    # 2. Desktop - /football
    print("\nLaunching Desktop Context...")
    context_desktop = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    page_desktop = context_desktop.new_page()
    try:
        page_desktop.goto('https://www.aiscore.com/football', timeout=30000)
        page_desktop.wait_for_timeout(3000)
        inspect_page(page_desktop, "Desktop /football")
    except Exception as e:
        print(f"Desktop failed: {e}")
        
    # 3. Desktop - /football/live
    print("\nLaunching Desktop Context (/live)...")
    try:
        page_desktop.goto('https://www.aiscore.com/football/live', timeout=30000)
        page_desktop.wait_for_timeout(3000)
        inspect_page(page_desktop, "Desktop /football/live")
    except Exception as e:
        print(f"Desktop /live failed: {e}")

    browser.close()
