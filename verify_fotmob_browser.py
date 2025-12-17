from playwright.sync_api import sync_playwright
import json
import time

def verify_fotmob_browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        
        def handle_response(response):
            try:
                if "application/json" in response.headers.get("content-type", ""):
                    # Capture Hidden API
                    if "api/frontend" in response.url or "matches" in response.url:
                        print(f"[INTERCEPT-API] {response.url}")
                        text = response.text()
                        print(f"Data Preview: {text[:500]}")
                        if "matches" in text:
                             print("[SUCCESS-API] Found 'matches' in response!")
            except:
                pass

        page.on("response", handle_response)

        print("[*] Navigating to fotmob.com (Warmup)...")
        page.goto("https://www.fotmob.com", wait_until="domcontentloaded")
        time.sleep(5)
        
        # Check SSR
        try:
            data = page.evaluate("window.__NEXT_DATA__")
            if data:
                print("[SUCCESS] Extracted __NEXT_DATA__")
                props = data.get('props', {})
                pageProps = props.get('pageProps', {})
                
                fallback = pageProps.get('fallback', {})
                print(f"Fallback Keys: {fallback.keys()}")
                
                # Check inside fallback
                for key, value in fallback.items():
                    print(f" - Key: {key}")
                    if isinstance(value, dict) and 'matches' in value:
                        matches = value['matches']
                        print(f"   [FOUND] {len(matches)} matches in {key}!")
                        for m in matches[:3]:
                             print(f"   - {m.get('home',{}).get('name')} vs {m.get('away',{}).get('name')}")
                             print(f"     Status: {m.get('status',{}).get('scoreStr')} (Live: {m.get('status',{}).get('live')})")
                             print(f"     GlobalId: {m.get('id')}")
        except Exception as e:
            print(f"[ERROR] SSR Extraction failed: {e}")
            
        # Try Direct API Access in Browser
        today = "20251217"
        api_url = f"https://www.fotmob.com/api/matches?date={today}&timezone=Asia/Kolkata&ccode3=IND"
        print(f"[*] Navigating to API: {api_url}")
        
        response = page.goto(api_url)
        print(f"[*] API Status: {response.status}")
        if response.status == 200:
            try:
                data = json.loads(page.inner_text("body"))
                if "leagues" in data:
                     print(f"[SUCCESS] API works! Found {len(data['leagues'])} leagues.")
                     print(f"[Sample League] {data['leagues'][0]['name']}")
            except:
                print("[FAIL] Could not parse API JSON")
        else:
             print(f"[FAIL] API returned {response.status}")

        browser.close()

if __name__ == "__main__":
    verify_fotmob_browser()
