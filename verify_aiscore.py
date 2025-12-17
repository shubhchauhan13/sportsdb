from playwright.sync_api import sync_playwright
import json
import time

def verify_aiscore():
    print("Verifying AiScore...")
    with sync_playwright() as p:
        # Use mobile emulation as often apps have cleaner APIs for mobile web
        iphone = p.devices['iPhone 12']
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            **iphone,
            locale='en-US',
            timezone_id='Asia/Kolkata'
        )
        
        page = context.new_page()
        
        target_url = "https://www.aiscore.com/cricket"
        print(f"[*] Navigating to {target_url}")
        
        api_dumps = []
        
        # Listen for API calls
        def handle_response(response):
            try:
                # Common AiScore API patterns
                # "api/match" or "list" or "live"
                if "api" in response.url and "json" in response.headers.get("content-type", ""):
                    print(f"[API] {response.url}")
                    try:
                        data = response.json()
                        api_dumps.append({
                            "url": response.url,
                            "data": data
                        })
                    except: pass
            except:
                pass
                
        page.on("response", handle_response)
        
        try:
            page.goto(target_url, timeout=60000, wait_until='networkidle')
            print("[*] Page loaded.")
            time.sleep(10) # Wait for live updates
            
            # Check title
            print(f"[*] Title: {page.title()}")
            
            # Dump captured API data
            if api_dumps:
                with open("aiscore_api_dump.json", "w") as f:
                    json.dump(api_dumps, f, indent=2)
                print(f"[SUCCESS] Dumped {len(api_dumps)} API responses to aiscore_api_dump.json")
            else:
                print("[WARN] No API responses captured")

            # NUXT Dump
            try:
                nuxt = page.evaluate("window.__NUXT__")
                if nuxt: 
                    print("[SUCCESS] Found window.__NUXT__ state")
                    with open("aiscore_data_live.json", "w") as f:
                        json.dump(nuxt, f, indent=2)
                    print("[INFO] Dumped __NUXT__ to aiscore_data_live.json")
            except Exception as e: 
                print(f"[WARN] NUXT extraction error: {e}")


                
            try:
                next_data = page.evaluate("window.__NEXT_DATA__")
                if next_data: 
                    print("[SUCCESS] Found window.__NEXT_DATA__")
            except: 
                pass
            
            # Take a screenshot to confirm it loaded (saved to disk, user can't see but useful for me if I refer to it)
            # page.screenshot(path="debug_aiscore.webp")
            
        except Exception as e:
            print(f"[ERROR] Navigation failed: {e}")
            
        browser.close()

if __name__ == "__main__":
    verify_aiscore()
