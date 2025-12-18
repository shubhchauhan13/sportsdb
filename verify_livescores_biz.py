from playwright.sync_api import sync_playwright

def verify_livescores_biz():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        url = "https://www.livescores.biz/live"
        print(f"Navigating to {url}...")
        try:
            page.goto(url, timeout=60000)
            print(f"Title: {page.title()}")
            
            # Check for match rows
            # Livescores.biz usually has tables
            
            rows = page.locator('tr').count()
            print(f"Table Rows: {rows}")
            
            # Try to print some match info
            if rows > 0:
                 # It might use 'game' class or just trs
                 count = 0
                 # Loop safely
                 matches = page.locator('.match-row_live').all()
                 if not matches:
                     matches = page.locator('tr[id*="match"]').all()
                     
                 print(f"Potential Match Rows (class/id): {len(matches)}")
                 
                 for m in matches[:5]:
                     txt = m.inner_text().replace('\n', ' ')
                     print(f"Match: {txt}")

        except Exception as e:
            print(f"Error: {e}")
            
        browser.close()

if __name__ == "__main__":
    verify_livescores_biz()
