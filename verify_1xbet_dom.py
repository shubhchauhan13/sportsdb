from playwright.sync_api import sync_playwright
import time

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Try mirrors if main site blocked
        urls = [
            "https://1xbet.com/live/ice-hockey",
            "https://melbet.com/live/ice-hockey",
            "https://22bet.com/live/ice-hockey"
        ]
        
        for url in urls:
            print(f"Checking {url}...")
            try:
                page.goto(url, timeout=30000)
                time.sleep(5)
                
                title = page.title()
                print(f"Title: {title}")
                
                # Check for match elements
                matches = page.locator('.c-events__item').count()
                print(f"Matches found (class .c-events__item): {matches}")
                
                if matches == 0:
                    matches = page.locator('.dashboard-game-block').count() 
                    print(f"Matches found (class .dashboard-game-block): {matches}")
                    
                if matches > 0:
                    print("✅ SUCCESS: Found matches")
                    # Dump first match html
                    first_match = page.locator('.c-events__item').first.inner_html()
                    print(f"First match HTML sample: {first_match[:200]}")
                    break
                    
            except Exception as e:
                print(f"Error: {e}")
                
        browser.close()

if __name__ == "__main__":
    run()
