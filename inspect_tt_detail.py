
from playwright.sync_api import sync_playwright
import json

def inspect_detail():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # ID from previous debug output
        mid = "l6keds4x6x0fv75" 
        # Using a generic URL structure that usually redirects correctly or loads
        url = f"https://www.aiscore.com/table-tennis/match/placeholder/placeholder/{mid}"
        
        print(f"Navigating to {url}...")
        page.goto(url, timeout=30000, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        
        data = page.evaluate("""() => {
            if (window.__NUXT__) return window.__NUXT__;
            return null;
        }""")
        
        if not data:
            print("No NUXT data on detail page.")
        else:
            state = data.get('state', {})
            # Look for match detail data
            # Key might be 'match' or 'matchDetail' or similar
            print("State keys:", list(state.keys()))
            
            # Check deep keys
            match_data = state.get('match', {}).get('match', {})
            if match_data:
                print("Found match data in state.match.match")
                if 'odds' in match_data:
                    print(f"Found 'odds' in matches: {match_data['odds']}")
                ext = match_data.get('ext', {})
                if 'odds' in ext:
                     print(f"Found 'ext.odds': {ext['odds']}")
                else:
                    print("No odds in match.ext")
            else:
                # Try finding where match data is
                print("Match data not found in obvious paths.")
                # print(json.dumps(state, indent=2)[:2000])

        browser.close()

if __name__ == "__main__":
    inspect_detail()
