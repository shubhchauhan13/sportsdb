from playwright.sync_api import sync_playwright
import time

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        urls = [
            "https://www.betexplorer.com/hockey/live/",
            "https://www.betexplorer.com/esports/live/"
        ]
        
        for url in urls:
            print(f"Checking {url}...")
            try:
                page.goto(url, timeout=30000, wait_until='domcontentloaded')
                time.sleep(5)
                
                title = page.title()
                print(f"Title: {title}")
                
                # Check for match rows
                rows = page.locator('.table-main__tr').count()
                print(f"Match rows found: {rows}")
                
                if rows > 0:
                    print("✅ SUCCESS: Found matches")
                    first_row = page.locator('.table-main__tr').first.inner_text()
                    print(f"First row text: {first_row}")
            except Exception as e:
                print(f"Error: {e}")
                
        browser.close()

if __name__ == "__main__":
    run()
