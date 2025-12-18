from playwright.sync_api import sync_playwright
import time

SOURCES = [
    {"name": "BeSoccer", "url": "https://www.besoccer.com/livescore", "selector": ".match-link"},
    {"name": "Soccer24", "url": "https://www.soccer24.com/", "selector": ".event__match"},
    {"name": "ESPN", "url": "https://www.espn.in/football/scoreboard", "selector": ".ScoreboardScoreCell"},
    {"name": "BBC Sport", "url": "https://www.bbc.com/sport/football/scores-fixtures", "selector": ".sp-c-fixture"},
    {"name": "Soccerway", "url": "https://us.soccerway.com/", "selector": ".match"},
    {"name": "Goal.com", "url": "https://www.goal.com/en/live-scores", "selector": ".match-main-data"},
    {"name": "Flashscore (Mobile)", "url": "https://m.flashscore.co.uk/", "selector": ".event__match"},
    {"name": "Livescore.cz", "url": "https://www.livescore.cz/", "selector": "table tr"},
    {"name": "Futbol24", "url": "https://m.futbol24.com/Live/", "selector": ".match"},
    {"name": "Xscores", "url": "https://m.xscores.com/", "selector": ".score_row"},
    {"name": "ScoreAxis", "url": "https://www.scoreaxis.com/", "selector": ".match-row"},
    {"name": "FootLive", "url": "https://footlive.me/", "selector": ".match_row"},
]

def mass_verify():
    with sync_playwright() as p:
        # Launch with stealth args
        browser = p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled']
        )
        
        # Helper to create context
        def get_page():
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            # Mask webdriver
            context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            return context.new_page()

        results = []
        
        print(f"Starting verification of {len(SOURCES)} sources...\n")
        
        for source in SOURCES:
            print(f"--- Testing {source['name']} ---")
            page = get_page()
            try:
                start = time.time()
                page.goto(source['url'], timeout=30000, wait_until='domcontentloaded')
                # Wait for potential dynamic content
                try: page.wait_for_selector(source['selector'], timeout=5000)
                except: pass
                
                title = page.title()
                count = page.locator(source['selector']).count()
                
                # Try generic fallback if 0
                if count == 0:
                     count = page.locator('tr').count()
                
                status = "✅ PASS" if count > 0 else "❌ FAIL"
                print(f"Status: {status} | Matches/Rows: {count} | Title: {title[:30]}...")
                
                results.append({
                    "name": source['name'],
                    "status": status,
                    "count": count,
                    "url": source['url']
                })
                
            except Exception as e:
                print(f"Status: ⚠️ ERROR | {str(e)[:50]}")
                results.append({"name": source['name'], "status": "ERROR", "count": 0})
            
            page.close()
            print("")
            
        browser.close()
        
        print("\n=== SUMMARY ===")
        for r in results:
            print(f"{r['name']}: {r['status']} ({r['count']} found)")

if __name__ == "__main__":
    mass_verify()
