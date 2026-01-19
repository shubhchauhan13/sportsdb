from playwright.sync_api import sync_playwright
import time

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Cricket.com Live Score
        url = "https://www.cricket.com/live-score"
        print(f"Navigating to {url}...")
        
        try:
            page.goto(url, wait_until='networkidle', timeout=60000)
            print(f"Title: {page.title()}")
            
            # Check for Session/Lambi keywords
            content = page.inner_text('body')
            if "Session" in content or "Lambi" in content or "CRR" in content:
                print("Found Keywords (Session/Lambi/CRR)!")
                print(content[:500])
            else:
                 print("Keywords not found.")

        except Exception as e:
            print(f"Error: {e}")
            
        browser.close()

if __name__ == "__main__":
    run()
