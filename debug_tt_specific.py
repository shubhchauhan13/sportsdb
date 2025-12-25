
from playwright.sync_api import sync_playwright

def check_tt_odds_specific():
    # ID: 15271045
    url = "https://www.sofascore.com/api/v1/event/15271045/odds/1/all"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        print(f"Fetching {url}")
        try:
            resp = page.goto(url)
            print(f"Status: {resp.status}")
            data = resp.json()
            markets = data.get('markets', [])
            print(f"Markets: {len(markets)}")
            for m in markets:
                print(f"Name: {m.get('marketName')} | Main: {m.get('isMain')}")
                choices = m.get('choices', [])
                for c in choices:
                    print(f"  - {c.get('name')}: {c.get('fractionalValue')}")
        except Exception as e:
            print(f"Error: {e}")
        browser.close()

if __name__ == "__main__":
    check_tt_odds_specific()
