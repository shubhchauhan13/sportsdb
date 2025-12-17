

from playwright.sync_api import sync_playwright
import json
import time

def verify_sofascore():
    with sync_playwright() as p:
        # Mobile Emulation Strategy
        iphone = p.devices['iPhone 12']
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-blink-features=AutomationControlled']
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale='en-US',
            timezone_id='Asia/Kolkata',
            extra_http_headers={
                 'Accept-Language': 'en-US,en;q=0.9',
            }
        )
        
        # --- Stealth Injection (The Pro Move) ---
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            window.chrome = { runtime: {} };
        """)
        
        page = context.new_page()

        # 1. Warmup (Crucial for Cookies & Trust)
        target_url = "https://www.sofascore.com/"
        print(f"[*] Visiting Homepage: {target_url}")
        
        # Check actual UA
        ua = page.evaluate("navigator.userAgent")
        print(f"[*] Actual User-Agent: {ua}")
        platform = page.evaluate("navigator.platform")
        print(f"[*] Actual Platform: {platform}")
        
        try:
            page.goto(target_url, timeout=60000, wait_until='domcontentloaded') # Faster than networkidle
            print("[*] Page loaded. Waiting 5s...")
            time.sleep(5)
            
            title = page.title()
            print(f"[*] Page Title: {title}")
            
            # Check for Cloudflare/Challenge text
            if "Just a moment" in title or "Challenge" in title:
                print("[!] CLOUDFLARE CHALLENGE DETECTED. Waiting 10s more...")
                time.sleep(10)
                print(f"[*] Post-wait Title: {page.title()}")
        except Exception as e:
            print(f"[ERROR] Warmup navigation failed: {e}")
            
    
        def handle_response(response):
            # Capture ALL JSON responses to see what's working
            try:
                if "application/json" in response.headers.get("content-type", ""):
                    print(f"[INTERCEPT] URL: {response.url} | Status: {response.status}")
                    if response.status == 200:
                        text = response.text()
                        if "events" in text:
                            print(f"[FOUND-EVENTS] This URL contains event data!")
                            # print(text[:200]) # Preview
            except:
                pass

        page.on("response", handle_response)

        # 3. Use UI Navigation to trigger requests
        target_url = "https://www.sofascore.com/cricket/live"
        print(f"[*] Navigating to UI: {target_url}")
        
        try:
            page.goto(target_url, timeout=60000, wait_until='domcontentloaded')
            print("[*] Page loaded. Checking for data blobs...")
            
            # Check for __NEXT_DATA__ or similar
            content = page.content()
            if "__NEXT_DATA__" in content:
                print("[SUCCESS] Found __NEXT_DATA__")
            if "window.__INITIAL_STATE__" in content:
                print("[SUCCESS] Found window.__INITIAL_STATE__")
            
            # Try to evaluate and get match count
            # Often data is in __NEXT_DATA__.props.pageProps.initialState...
            try:
                data = page.evaluate("""() => {
                    if (window.__NEXT_DATA__) return window.__NEXT_DATA__;
                    return null;
                }""")
                if data:
                    print("[DATA] Extracted __NEXT_DATA__")
                    # Inspect Structure
                    try:
                        props = data.get('props', {})
                        pageProps = props.get('pageProps', {})
                        print(f"PageProps Keys: {pageProps.keys()}")
                        
                        initialState = pageProps.get('initialState', {})
                        print(f"InitialState Keys: {initialState.keys()}")
                        
                        initialProps = pageProps.get('initialProps', {})
                        print(f"InitialProps Keys: {initialProps.keys()}")
                        
                        # Check deep keys
                        # Sometimes it's in a dehydrated state
                    except Exception as e:
                        print(f"Error inspecting data: {e}")
                else:
                    print("[FAIL] __NEXT_DATA__ object not found in JS context")
            except Exception as e:
                print(f"[WARN] JS Eval failed: {e}")

        except Exception as e:
            print(f"[ERROR] Logic failed: {e}")
            
        browser.close()

if __name__ == "__main__":
    verify_sofascore()


