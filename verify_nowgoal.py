from playwright.sync_api import sync_playwright

def verify_nowgoal():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Valid NowGoal mirrors
        urls = [
            "https://live.nowgoal8.com/",
            "http://www.nowgoal.com/"
        ]
        
        for url in urls:
            print(f"Checking {url}...")
            try:
                page.goto(url, timeout=30000)
                print(f"Title: {page.title()}")
                
                # NowGoal uses tables with id="table_live" usually
                count = page.locator('#table_live').count()
                if count == 0:
                    count = page.locator('table').count()
                    
                print(f"Tables: {count}")
                
                if count > 0:
                    print("Found tables on NowGoal!")
                    break 
            except Exception as e:
                print(f"Error: {e}")
            
        browser.close()

if __name__ == "__main__":
    verify_nowgoal()
