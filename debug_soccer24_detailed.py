from playwright.sync_api import sync_playwright
import time

def debug_soccer24():
    with sync_playwright() as p:
        print("Launching browser...")
        browser = p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled']
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        page = context.new_page()
        
        url = "https://www.soccer24.com/"
        print(f"Navigating to {url}...")
        
        try:
            page.goto(url, timeout=60000, wait_until='domcontentloaded')
            print("Page loaded. Waiting for .event__match...")
            
            try:
                page.wait_for_selector('.event__match', timeout=10000)
                print("Selector found!")
            except:
                print("Timeout waiting for .event__match")
            
            # Check for any content
            title = page.title()
            print(f"Page Title: {title}")
            
            # Dump HTML snippet if no matches
            content = page.content()
            if "Challenge Validation" in content or "Cloudflare" in title:
                print("BLOCKED BY CLOUDFLARE")
            
            rows = page.locator('.event__match').all()
            print(f"Found {len(rows)} event rows.")
            
            for i, row in enumerate(rows[:3]):
                print(f"--- Row {i} ---")
                try:
                    print("HTML:", row.inner_html())
                    home = row.locator('.event__participant--home').inner_text()
                    print(f"Home: {home}")
                except Exception as e:
                    print(f"Row Error: {e}")
                    
        except Exception as e:
            print(f"Global Error: {e}")
            
        browser.close()

if __name__ == "__main__":
    debug_soccer24()
