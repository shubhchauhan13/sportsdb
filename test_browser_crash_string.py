from playwright.sync_api import sync_playwright
import time

def test_crash():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print("Browser started. Closing browser manually...")
        browser.close()
        
        try:
            print("Attempting validation on closed browser...")
            page.set_extra_http_headers({"User-Agent": "test"})
        except Exception as e:
            print(f"CAUGHT ERROR: {e}")

        try:
            print("Attempting goto on closed browser...")
            page.goto("http://example.com")
        except Exception as e:
            print(f"CAUGHT ERROR: {e}")

if __name__ == "__main__":
    test_crash()
