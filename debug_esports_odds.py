
from playwright.sync_api import sync_playwright

def check_esports_odds_specific():
    # ID: 15257053
    # Url: https://www.sofascore.com/api/v1/event/15257053/odds/1/all
    url = "https://www.sofascore.com/api/v1/event/15257053/odds/1/all"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        print(f"Fetching {url}")
        try:
            resp = page.goto(url)
            print(f"Status: {resp.status}")
            data = resp.json()
            # print(data)
            markets = data.get('markets', [])
            print(f"Markets: {len(markets)}")
            for m in markets:
                print(m.get('marketName'))
        except Exception as e:
            print(f"Error: {e}")
        browser.close()

if __name__ == "__main__":
    check_esports_odds_specific()
