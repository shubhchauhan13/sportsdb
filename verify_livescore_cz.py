from playwright.sync_api import sync_playwright

def verify_alternatives():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        # 1. Livescore.cz
        page = browser.new_page()
        try:
            print("Checking Livescore.cz...")
            page.goto("https://www.livescore.cz/", timeout=60000, wait_until='networkidle')
            print(f"Title: {page.title()}")
            rows = page.locator(".match").count() # Hypothetical class
            if rows == 0: rows = page.locator("tr").count()
            print(f"Rows: {rows}")
            
            # Print sample text
            # Check tables
            tables = page.locator("table").count()
            print(f"Tables: {tables}")
            
            if tables > 0:
                html = page.locator("table").first.inner_html()
                print(f"Table HTML snippet: {html[:500]}")
                
        except Exception as e:
            print(f"CZ Error: {e}")
            
        # 2. m.aiscore.com
        page2 = browser.new_page(
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1"
        )
        try:
            print("\nChecking m.aiscore.com...")
            # Note: redirects often happen
            page2.goto("https://m.aiscore.com/football", timeout=40000)
            page2.wait_for_timeout(5000)
            print(f"Title: {page2.title()}")
            
            # Check NUXT or Text
            data = page2.evaluate("() => { if (window.__NUXT__) return window.__NUXT__; return null; }")
            if data:
                print("NUXT Found on m.aiscore")
                # check matches
                state = data.get('state', {})
                fb = state.get('football', {})
                matches = fb.get('matchesData_matches', [])
                print(f"m.aiscore matches: {len(matches)}")
            else:
                print("NUXT NOT found on m.aiscore")
                # Text check
                content = page2.content()
                if "An Error Occured" in content:
                    print("Error detected on m.aiscore")
                elif "Shahdagh" in content:
                    print("Match text found on m.aiscore!")

        except Exception as e:
            print(f"m.aiscore Error: {e}")
            
        browser.close()

if __name__ == "__main__":
    verify_alternatives()
