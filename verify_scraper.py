from playwright.sync_api import sync_playwright
import time
import sys

# Import the module to test
# We need to make sure we don't start the server by importing
import scraper_service

def verify_scraping():
    print("Verifying Scraper Logic...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
             user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        # Test Fixtures Page
        url = "https://crex.com/fixtures/match-list"
        print(f"Testing URL: {url}")
        
        # Listen for console logs
        page.on("console", lambda msg: print(f"BROWSER: {msg.text}"))
        
        # Call the function from the module
        # But we need to debug, so let's manually do the goto first to dump
        page.goto(url, timeout=60000)
        time.sleep(5)
        with open("debug_fixtures.html", "w") as f:
            f.write(page.content())
        print("Dumped HTML to debug_fixtures.html")

        scraper_service.scrape_mappings_from_url(page, url)
        
        # Check Cache
        team_count = len(scraper_service.TEAM_CACHE)
        league_count = len(scraper_service.LEAGUE_CACHE)
        
        print(f"TEAM_CACHE Size: {team_count}")
        print(f"LEAGUE_CACHE Size: {league_count}")
        
        if team_count > 0:
            print("Sample Teams:")
            for k, v in list(scraper_service.TEAM_CACHE.items())[:5]:
                print(f"  {k}: {v}")
                
        if league_count > 0:
            print("Sample Leagues:")
            for k, v in list(scraper_service.LEAGUE_CACHE.items())[:5]:
                print(f"  {k}: {v}")
        
        browser.close()
        
        if team_count == 0:
            print("FAILURE: No teams found. Scraper logic might be broken.")
            sys.exit(1)
        else:
            print("SUCCESS: Teams extracted.")

if __name__ == "__main__":
    verify_scraping()
