
from playwright.sync_api import sync_playwright

def dump_html():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        # Generic URL validation
        url = "https://www.aiscore.com/table-tennis/match/piotr-staniszewski-vs-iwasyszyn-wojciech/l6keds4x6x0fv75"
        print(f"Fetching {url}")
        try:
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            content = page.content()
            
            with open("tt_detail.html", "w") as f:
                f.write(content)
                
            print(f"Dumped {len(content)} bytes.")
            
            # Quick check
            if "oddItems" in content:
                print("FOUND 'oddItems' in HTML!")
            elif "odds" in content:
                print("Found 'odds' keyword in HTML (could be UI text).")
            else:
                print("No 'odds' found in HTML.")
                
        except Exception as e:
            print(f"Error: {e}")
            
        browser.close()

if __name__ == "__main__":
    dump_html()
