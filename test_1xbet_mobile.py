from playwright.sync_api import sync_playwright
import time

def run():
    with sync_playwright() as p:
        # Use iPhone emulation
        iphone = p.devices['iPhone 12']
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(**iphone)
        page = context.new_page()
        
        urls = [
            "https://1xbet.com/live/ice-hockey",
            "https://1xstavka.ru/live/ice-hockey",
            "https://lite.1xbet.com/live/ice-hockey"
        ]
        
        for url in urls:
            print(f"Checking {url}...")
            try:
                page.goto(url, timeout=20000, wait_until='domcontentloaded')
                time.sleep(5)
                
                title = page.title()
                print(f"Title: {title}")
                
                content = page.content()
                if "Access Denied" in content or "403 Forbidden" in title:
                    print("❌ Blocked")
                    continue
                    
                matches = page.locator('.c-events__item').count()
                if matches == 0:
                     matches = page.locator('.dashboard-game-block').count()
                     
                print(f"Matches found: {matches}")
                
                if matches > 0:
                    print("✅ SUCCESS: Found matches on mobile")
                    break
                    
            except Exception as e:
                print(f"Error: {e}")
                
        browser.close()

if __name__ == "__main__":
    run()
