from playwright.sync_api import sync_playwright
from playwright_stealth.stealth import Stealth
import json
import time

def test_aiscore():
    with sync_playwright() as p:
        # Add stealth args
        args = [
            '--disable-blink-features=AutomationControlled',
            '--disable-infobars',
        ]
        browser = p.chromium.launch(headless=True, args=args)
        page = browser.new_page()
        
        # Apply Stealth
        Stealth().apply_stealth_sync(page)

        
        url = "https://www.aiscore.com/football/live"
        print(f"Navigating to {url}...")
        
        try:
            page.goto(url, timeout=60000, wait_until='domcontentloaded')
            print("Waiting 15s for Cloudflare challenge...")
            page.wait_for_timeout(15000) # Increased to 15s
            
            # Check Title
            print(f"Page Title: {page.title()}")
            
            # 1. Try __NUXT__ extraction (Current Method)
            data = page.evaluate("""() => {
                if (window.__NUXT__) return window.__NUXT__;
                return null;
            }""")
            
            if data:
                print("[SUCCESS] __NUXT__ object found!")
                # Shallow validation
                state = data.get('state', {})
                print(f"State keys: {list(state.keys())}")
            else:
                print("[FAIL] __NUXT__ object NOT found.")
                
            # 2. Visual Check (Screenshots helpful, but here we just check selectors)
            # Check if match list exists
            matches = page.locator('.match-list-item, div[class*="matchItem"]').count()
            print(f"Visual Elements Found (Current Selector estimate): {matches}")
            
        except Exception as e:
            print(f"[ERROR] {e}")
            
        browser.close()

if __name__ == "__main__":
    test_aiscore()
