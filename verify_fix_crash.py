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
            if res == []:
                print("SUCCESS: Returned empty list.")
            else:
                print(f"FAILURE: Returned {res}")
        except Exception as e:
            print(f"FAILURE: Crashed with {e}")

        # Test 2: fetch_sofascore_esports
        print("\nTesting fetch_sofascore_esports...")
        try:
            res = scraper_service.fetch_sofascore_esports(page)
            if res == []:
                print("SUCCESS: Returned empty list.")
            else:
                print(f"FAILURE: Returned {res}")
        except Exception as e:
            print(f"FAILURE: Crashed with {e}")

        # Test 3: fetch_oddsportal_generic
        print("\nTesting fetch_oddsportal_generic...")
        try:
            res = scraper_service.fetch_oddsportal_generic(page, 'handball', 6)
            if res == []:
                print("SUCCESS: Returned empty list.")
            else:
                print(f"FAILURE: Returned {res}")
        except Exception as e:
            print(f"FAILURE: Crashed with {e}")

if __name__ == "__main__":
    verify_graceful_failure()
