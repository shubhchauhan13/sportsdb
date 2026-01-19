from playwright.sync_api import sync_playwright
import time

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Betfair Exchange - Cricket
        url = "https://www.betfair.com/exchange/plus/cricket"
        print(f"Navigating to {url}...")
        
        try:
            page.goto(url, wait_until='networkidle', timeout=60000)
            print(f"Title: {page.title()}")
            
            # Look for match links
            # Usually generic links
            content = page.inner_text('body')
            if "In-Play" in content:
                print("Found In-Play section.")
            
            # Try to find a link to a match
            # Selector is tricky, checking for any market group
            matches = page.locator(".coupon-card-wrapper").all()
            print(f"Found {len(matches)} potential matches on listing.")
            
            if matches:
               # Click the first one
               matches[0].click()
               time.sleep(5)
               
               # Now look for markets
               # "6 Over Line" or "1st Innings Runs"
               match_content = page.inner_text('body')
               if "6 Over" in match_content or "Innings Runs" in match_content:
                   print("FOUND Session/Lambi markers (6 Overs / Innings Runs)!")
                   
                   # Try to grab the values
                   # This requires specific selectors, but just knowing it exists is step 1
                   print("Text Snippet:")
                   print(match_content[:1000])

        except Exception as e:
            print(f"Error: {e}")
            
        browser.close()

if __name__ == "__main__":
    run()
