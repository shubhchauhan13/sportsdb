from playwright.sync_api import sync_playwright
import time

def check_site(page, url, name):
    print(f"Checking {name} at {url}...")
    try:
        response = page.goto(url, timeout=20000, wait_until='domcontentloaded')
        title = page.title()
        print(f"[{name}] Title: {title} | Status: {response.status}")
        
        # Check for specific indicators
        if "sofascore" in name.lower():
            # Check for events list or something generic
            # Sofascore often has api calls we can spy on, but here just checking page load
             try:
                page.wait_for_selector('div[class*="EventCell"]', timeout=5000)
                print(f"  [{name}] Found event cells (likely has content).")
             except:
                print(f"  [{name}] No event cells found immediately.")

        if "flashscore" in name.lower():
             try:
                page.wait_for_selector('.sportName', timeout=5000)
                print(f"  [{name}] Found .sportName (likely has content).")
             except:
                print(f"  [{name}] No .sportName found.")
                
        return True

    except Exception as e:
        print(f"[{name}] Error: {e}")
        return False

def explore_alternatives():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        sites = [
            ("Sofascore MMA", "https://www.sofascore.com/mma"),
            ("Flashscore MMA", "https://www.flashscore.com/mma/"),
            ("Flashscore UFC", "https://www.flashscore.com/mma/ufc/"),
            ("Livesport MMA", "https://www.livesport.com/mma/")
        ]
        
        for name, url in sites:
            check_site(page, url, name)
            time.sleep(2)
            
        browser.close()

if __name__ == "__main__":
    explore_alternatives()
