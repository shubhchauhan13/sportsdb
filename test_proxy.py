from playwright.sync_api import sync_playwright
import time
import datetime

PROXY_CONFIG = {
    'server': 'http://gw.dataimpulse.com:823',
    'username': '448ee9fc87025dfdc8ab',
    'password': 'f8fd876b005c06f1'
}

def test_proxy():
    print(f"[{datetime.datetime.now()}] Starting Proxy Test...")
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(
                headless=True, 
                proxy=PROXY_CONFIG
            )
            page = browser.new_page()
            
            start = time.time()
            print("Navigating to httpbin.org/ip...")
            
            # 30s timeout
            response = page.goto("https://httpbin.org/ip", timeout=30000)
            
            elapsed = time.time() - start
            print(f"[{datetime.datetime.now()}] Response received in {elapsed:.2f}s")
            
            if response.ok:
                print(f"Status: {response.status}")
                print(f"Body: {response.text()}")
            else:
                print(f"Failed: {response.status}")
                
            browser.close()
            
        except Exception as e:
            print(f"[{datetime.datetime.now()}] Proxy Test Failed: {e}")

if __name__ == "__main__":
    test_proxy()
