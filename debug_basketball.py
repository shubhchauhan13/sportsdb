from playwright.sync_api import sync_playwright
import json

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    page = context.new_page()
    
    print("Navigating to Basketball (Desktop)...")
    try:
        page.goto('https://www.aiscore.com/basketball', timeout=30000)
        page.wait_for_timeout(3000)
        
        data = page.evaluate("() => window.__NUXT__")
        if data:
            state = data.get('state', {})
            sport_state = state.get('basketball', {})
            
            # Check matches
            matches = sport_state.get('matchesData_matches', [])
            print(f"Found {len(matches)} matches.")
            
            if matches:
                m = matches[0]
                print(f"Sample Match ID: {m.get('id')}")
                print(f"Home Team Obj: {m.get('homeTeam')}")
                print(f"Away Team Obj: {m.get('awayTeam')}")
                
            # Check teams map
            teams_list = sport_state.get('matchesData_teams', [])
            print(f"Found {len(teams_list)} entries in team map.")
            if teams_list:
                print(f"Sample Team: {teams_list[0]}")
                
        else:
            print("No __NUXT__")
            
    except Exception as e:
        print(f"Error: {e}")
        
    browser.close()
