from playwright.sync_api import sync_playwright
import json
import time

def verify_cricbuzz_browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        def handle_response(response):
            try:
                if "application/json" in response.headers.get("content-type", ""):
                    print(f"[INTERCEPT] URL: {response.url}")
                    # Check for keywords
                    if "matches" in response.url or "live" in response.url:
                        print(f"[POTENTIAL-API] {response.url}")
                        try:
                            text = response.text()
                            if "matchId" in text or "seriesName" in text:
                                print("[SUCCESS] Found Match Data Payload!")
                                # print(text[:200])
                        except:
                            pass
            except:
                pass

        page.on("response", handle_response)

        print("[*] Navigating to cricbuzz live scores...")
        page.goto("https://www.cricbuzz.com/cricket-match/live-scores", wait_until="networkidle")
        time.sleep(5)
        browser.close()

if __name__ == "__main__":
    verify_cricbuzz_browser()
