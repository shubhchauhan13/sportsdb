from playwright.sync_api import sync_playwright
import json
import time

def inspect_sofascore():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Use a stealthy context
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)
        
        page = context.new_page()
        
        try:
            url = "https://www.sofascore.com/cricket/live"
            print(f"[*] Navigating to {url}")
            page.goto(url, timeout=60000, wait_until='networkidle')
            
            # Dump __NEXT_DATA__
            print("[*] Extracting __NEXT_DATA__...")
            data = page.evaluate("() => window.__NEXT_DATA__")
            
            if data:
                with open("sofascore_next_data.json", "w") as f:
                    json.dump(data, f, indent=2)
                print("[SUCCESS] Dumped to sofascore_next_data.json")
                
                # Print keys for quick preview
                props = data.get('props', {})
                pageProps = props.get('pageProps', {})
                print(f"PageProps Keys: {pageProps.keys()}")
                
                initialState = pageProps.get('initialState', {})
                print(f"InitialState Keys: {initialState.keys()}")
                
                # Check for live events in initialState
                for key, val in initialState.items():
                    if isinstance(val, dict):
                         print(f"  > {key} keys: {val.keys()}")
                         
            else:
                print("[FAIL] __NEXT_DATA__ is null")
                
        except Exception as e:
            print(f"[ERROR] {e}")
            
        browser.close()

if __name__ == "__main__":
    inspect_sofascore()
