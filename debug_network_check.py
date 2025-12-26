from playwright.sync_api import sync_playwright
import time

URLS = [
    "https://www.aiscore.com/american-football",
    "https://www.oddsportal.com/water-polo/live/",
    "https://www.oddsportal.com/snooker/live/"
]

def check_urls():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        for url in URLS:
            print(f"Testing {url}...")
            start = time.time()
            try:
                page.goto(url, timeout=10000, wait_until='domcontentloaded')
                print(f"  [SUCCESS] Loaded in {time.time() - start:.2f}s")
            except Exception as e:
                print(f"  [FAIL] {e}")
        
        browser.close()

if __name__ == "__main__":
    check_urls()
