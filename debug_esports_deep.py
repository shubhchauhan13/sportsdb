
from playwright.sync_api import sync_playwright
import json

def debug_esports_deep():
    targets = [
        {"id": "15257053", "sys": "sf"},
        {"id": "15267408", "sys": "sf"},
        {"id": "15248828", "sys": "sf"}
    ]
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        for t in targets:
            mid = t['id']
            print(f"\n--- Checking {mid} ---")
            
            # 1. Check Standard Odds (Provider 1)
            u1 = f"https://www.sofascore.com/api/v1/event/{mid}/odds/1/all"
            try:
                r = page.goto(u1)
                if r.ok:
                    print("FOUND ODDS at standard endpoint!")
                    print(r.json())
                else:
                    print(f"Standard odds 404")
            except: pass
            
            # 2. Check Providers List
            u2 = f"https://www.sofascore.com/api/v1/event/{mid}/odds/providers"
            try:
                r = page.goto(u2)
                if r.ok:
                    provs = r.json()
                    print(f"Providers found: {provs}")
                    # If we find providers, check them!
                    for k in provs.keys():
                        if k != '1':
                             u_alt = f"https://www.sofascore.com/api/v1/event/{mid}/odds/{k}/all"
                             print(f"Checking alt provider {k}: {u_alt}")
                             r2 = page.goto(u_alt)
                             if r2.ok:
                                 print(f"FOUND ODDS with provider {k}!")
                                 print(r2.json())
                else:
                     print("No providers info.")
            except: pass
            
            # 3. Check Event Detail for 'winningOdds'
            u3 = f"https://www.sofascore.com/api/v1/event/{mid}"
            try:
                r = page.goto(u3)
                if r.ok:
                    d = r.json()
                    print(f"Event Data keys: {d.keys()}")
                    evt = d.get('event', {})
                    print(f"WinningOdds: {d.get('winningOdds')}")
            except: pass

        browser.close()

if __name__ == "__main__":
    debug_esports_deep()
