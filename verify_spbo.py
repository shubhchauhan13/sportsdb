from playwright.sync_api import sync_playwright

def verify_spbo():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        url = "https://www.spbo.com/"
        print(f"Navigating to {url}...")
        
        try:
            page.goto(url, timeout=60000)
            page.wait_for_timeout(5000)
            
            print(f"Title: {page.title()}")
            
            # SPBO typically has a table with many matches
            # Look for table rows
            # The structure is usually simple <table> <tr>...
            
            rows = page.locator('tr').count()
            print(f"Total Table Rows found: {rows}")
            
            # Try to grab some text from rows to see if it's match data
            # Format often: Time | Home | Score | Away
            
            # Get first 5 valid rows with content
            count = 0
            all_rows = page.locator('tr').all()
            for r in all_rows:
                text = r.inner_text().replace('\n', ' ')
                if "Live" in text or ":" in text: # rudimentary check
                     print(f"Row: {text[:100]}...")
                     count += 1
                     if count > 5: break
            
        except Exception as e:
            print(f"Error: {e}")
            
        browser.close()

if __name__ == "__main__":
    verify_spbo()
