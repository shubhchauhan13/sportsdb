from playwright.sync_api import sync_playwright

def verify_futbol24():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Use iPhone emulation for mobile site + Ignore SSL
        iphone = p.devices['iPhone 12']
        context = browser.new_context(**iphone, ignore_https_errors=True)
        page = context.new_page()
        
        url = "https://m.futbol24.com/Live/?__lang=en"
        print(f"Navigating to {url}...")
        try:
            page.goto(url, timeout=60000)
            print(f"Title: {page.title()}")
            
            # Check for match containers
            # Usually simple table or div list
            # Look for '.match' or 'tr'
            
            count = page.locator('.match').count()
            print(f"'.match' elements: {count}")
            
            if count == 0:
                 # Check for 'div.l' (live?) or simply verify text
                 content = page.content()
                 if "Live" in content:
                     print("Text 'Live' found in content.")
                 
                 # list items?
                 lis = page.locator('li').count()
                 print(f"List items: {lis}")
                 
                 # Try printing some text
                 if lis > 0:
                     for i in range(min(5, lis)):
                         print(f"Item {i}: {page.locator('li').nth(i).inner_text().strip()}")
            
            if count > 0:
                print("Sample Matches:")
                all_m = page.locator('.match').all()
                for m in all_m[:5]:
                    txt = m.inner_text().replace('\n', ' | ')
                    print(f"Match: {txt}")

        except Exception as e:
            print(f"Error: {e}")
            
        browser.close()

if __name__ == "__main__":
    verify_futbol24()
