from playwright.sync_api import sync_playwright
import json
import time

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # CREX Live Matches Page
        url = "https://crex.live/fixtures/match-list"
        print(f"Navigating to {url}...")
        
        try:
            page.goto(url, wait_until='networkidle', timeout=60000)
            
            # Print title
            print(f"Title: {page.title()}")
            
            # Check for any "Session" text on page
            body_text = page.inner_text("body")
            if "Session" in body_text or "Lambi" in body_text:
                print("FOUND 'Session' or 'Lambi' keyword on page!")
            else:
                print("Keywords 'Session'/'Lambi' NOT found on match listing.")
                
            # Try to click the first LIVE match to see details
            # Selector is a guess, finding a link with '/scoreboard' or '/live'
            # usually matches links are <a> tags
            links = page.locator("a[href*='/scoreboard']").all()
            if links:
                print(f"Found {len(links)} match links. Visiting first one...")
                first_link = links[0].get_attribute('href')
                full_link = f"https://crex.live{first_link}" if first_link.startswith('/') else first_link
                print(f"Visiting Match: {full_link}")
                
                page.goto(full_link, wait_until='domcontentloaded')
                time.sleep(5)
                
                # Check specifics in match detail
                detail_text = page.inner_text("body")
                 # Look for 'Min' 'Max' 'Over' which usually indicates session
                if "Min" in detail_text and "Max" in detail_text:
                     print("Found 'Min'/'Max' text - likely Session Odds!")
                
                print("Page Text Snippet 500 chars:")
                print(detail_text[:500])

        except Exception as e:
            print(f"Error: {e}")
            
        browser.close()

if __name__ == "__main__":
    run()
