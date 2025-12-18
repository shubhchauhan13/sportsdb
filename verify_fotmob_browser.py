from playwright.sync_api import sync_playwright
import json

def verify_fotmob_browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Intercept network requests
        page.on("request", lambda request: print(f">> {request.method} {request.url}") if "api" in request.url else None)
        
        # FotMob Matches
        url = "https://www.fotmob.com/"
        print(f"[*] Navigating to: {url}")
        
        try:
            page.goto(url, timeout=30000)
            page.wait_for_timeout(5000)
            
            # Click on 'Matches' or verify content
            print("[*] Page loaded. checking content.")
            
        except Exception as e:
            print(f"[ERROR] {e}")
            
        browser.close()

if __name__ == "__main__":
    verify_fotmob_browser()
