
from playwright.sync_api import sync_playwright

def debug_live_page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            print("Navigating to live-cricket-scores...")
            page.goto("https://crex.com/live-cricket-scores", timeout=60000)
            page.wait_for_timeout(5000)
            
            content = page.content()
            with open("debug_live_page.html", "w") as f:
                f.write(content)
            print("Saved debug_live_page.html")
            
            # Try to print the script content length
            script = page.locator("script#app-root-state")
            if script.count() > 0:
                text = script.text_content()
                print(f"Script content length: {len(text)}")
                print(f"Sample: {text[:200]}...")
            else:
                print("Script #app-root-state NOT FOUND")
                
        except Exception as e:
            print(f"Error: {e}")
        browser.close()

if __name__ == "__main__":
    debug_live_page()
