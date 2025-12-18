from playwright.sync_api import sync_playwright
import json

def dump_structure():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Use Desktop for everything for stability in debug
        context = browser.new_context(
             user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        # 1. BASKETBALL
        print("Inspecting Basketball...")
        try:
            page.goto('https://www.aiscore.com/basketball', timeout=60000)
            page.wait_for_timeout(5000)
            data = page.evaluate("() => { if(window.__NUXT__) return window.__NUXT__; return null; }")
            
            if data and 'state' in data:
                matches = data['state'].get('basketball', {}).get('matchesData_matches', [])
                print(f"Basketball matches found: {len(matches)}")
                if matches:
                    # Find LIVE match
                    live_m = next((m for m in matches if m.get('matchStatus') == 2), None)
                    if live_m:
                        print("=== LIVE BASKETBALL MATCH ===")
                        print(json.dumps(live_m, indent=2))
                    else:
                        print("No LIVE Basketball match. Dumping first match:")
                        print(json.dumps(matches[0], indent=2))
            else:
                print("No __NUXT__ for Basketball")
        except Exception as e:
            print(f"Basketball Error: {e}")

        # 2. TENNIS
        print("\nInspecting Tennis...")
        try:
            page.goto('https://www.aiscore.com/tennis', timeout=60000)
            page.wait_for_timeout(5000)
            data = page.evaluate("() => { if(window.__NUXT__) return window.__NUXT__; return null; }")
            
            if data and 'state' in data:
                matches = data['state'].get('tennis', {}).get('matchesData_matches', [])
                print(f"Tennis matches found: {len(matches)}")
                if matches:
                    live_m = next((m for m in matches if m.get('matchStatus') == 2), None)
                    if live_m:
                        print("=== LIVE TENNIS MATCH ===")
                        print(json.dumps(live_m, indent=2))
                    else:
                        print("No LIVE Tennis match. Dumping first match:")
                        print(json.dumps(matches[0], indent=2))
            else:
                 print("No __NUXT__ for Tennis")
        except Exception as e:
            print(f"Tennis Error: {e}")

        browser.close()

if __name__ == "__main__":
    dump_structure()
