from playwright.sync_api import sync_playwright
import scraper_service
import sys

def verify_graceful_failure():
    print("Verifying Scraper Graceful Failure on Closed Browser...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print("Browser started. Closing browser manually...")
        browser.close()
        
        # Test 1: fetch_sofascore_table_tennis
        print("\nTesting fetch_sofascore_table_tennis...")
        try:
            res = scraper_service.fetch_sofascore_table_tennis(page)
            # If it returns, check if empty
            if res:
                print(f"FAILURE: Returned non-empty: {res}")
            else:
                print("SUCCESS: Returned empty/None (unexpected but safe).")
        except Exception as e:
            if "target page, context or browser has been closed" in str(e).lower() or "browser has been closed" in str(e).lower():
                 print(f"SUCCESS: Function correctly raised closed browser exception: {e}")
            else:
                 print(f"FAILURE: Crashed with unexpected error: {e}")

        # Test 2: fetch_sofascore_esports
        print("\nTesting fetch_sofascore_esports...")
        try:
            res = scraper_service.fetch_sofascore_esports(page)
            if res:
                print(f"FAILURE: Returned non-empty: {res}")
            else:
                print("SUCCESS: Returned empty/None (unexpected but safe).")
        except Exception as e:
            if "target page, context or browser has been closed" in str(e).lower() or "browser has been closed" in str(e).lower():
                 print(f"SUCCESS: Function correctly raised closed browser exception: {e}")
            else:
                 print(f"FAILURE: Crashed with unexpected error: {e}")

        # Test 3: fetch_oddsportal_generic
        print("\nTesting fetch_oddsportal_generic...")
        try:
            res = scraper_service.fetch_oddsportal_generic(page, 'handball', 6)
            if res:
                print(f"FAILURE: Returned non-empty: {res}")
            else:
                print("SUCCESS: Returned empty/None (unexpected but safe).")
        except Exception as e:
            if "target page, context or browser has been closed" in str(e).lower() or "browser has been closed" in str(e).lower():
                 print(f"SUCCESS: Function correctly raised closed browser exception: {e}")
            else:
                 print(f"FAILURE: Crashed with unexpected error: {e}")

if __name__ == "__main__":
    verify_graceful_failure()
