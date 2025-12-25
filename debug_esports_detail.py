
from playwright.sync_api import sync_playwright
import json

def debug_esports_detail():
    # ID: 15262738 (from previous history check)
    url = "https://www.sofascore.com/api/v1/event/15262738"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print(f"Fetching Detail: {url}")
        resp = page.goto(url)
        if resp.ok:
            data = resp.json()
            print("Detail Data Keys:", data.get('event', {}).keys())
            # Check for 'vote' or 'winningOdds'?
            print("Vote:", data.get('vote'))
            print("WinningOdds:", data.get('winningOdds'))
        else:
            print(f"Detail fetch failed: {resp.status}")
            
        browser.close()

if __name__ == "__main__":
    debug_esports_detail()
