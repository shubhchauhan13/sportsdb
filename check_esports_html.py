
from playwright.sync_api import sync_playwright

def check_esports_html():
    # URL for the match found: pipsqueak-plus-4-l1ga-team/OAEsYlK
    # ID: 15257053
    url = "https://www.sofascore.com/pipsqueak-plus-4-l1ga-team/OAEsYlK"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        print(f"Navigating to {url}...")
        page.goto(url, timeout=30000)
        
        # Take a screenshot to visualize
        page.screenshot(path="esports_check.png")
        print("Screenshot saved.")
        
        # Check text for odds
        content = page.content()
        if "odds" in content:
            print("Found 'odds' in HTML.")
        else:
            print("No 'odds' in HTML.")
            
        browser.close()

if __name__ == "__main__":
    check_esports_html()
