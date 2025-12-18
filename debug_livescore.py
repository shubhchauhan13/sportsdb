from playwright.sync_api import sync_playwright

def val_livescore():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print("Navigating to LiveScore Football...")
        try:
            # LiveScore Football Live
            url = "https://www.livescore.com/en/football/live/"
            page.goto(url, timeout=40000)
            page.wait_for_timeout(5000)
            
            # Check for match rows (LiveScore class names are usually dynamic or simple)
            # Look for typical time/score elements
            
            # Debug title
            print(f"Title: {page.title()}")
            
            # Try to find match containers. LiveScore usually has 'MatchRow' or similar IDs/Classes
            # Let's count potential matches
            # Class examples: 'MatchRow-sc-...', 'Score-sc-...'
            # We'll select by generic ID or role if possible, or print body text to regex
            
            content = page.content()
            if "No live matches" in content:
                print("No live matches found on page text.")
            else:
                print("Live matches might be present.")
                
            # Extract basic text of first few matches
            rows = page.locator('div[data-testid*="match-row"]').all()
            print(f"Found {len(rows)} Match Rows (via data-testid).")
            
            if rows:
                print(f"Sample Text: {rows[0].inner_text()}")
                
        except Exception as e:
            print(f"Error: {e}")
            
        browser.close()

if __name__ == "__main__":
    val_livescore()
