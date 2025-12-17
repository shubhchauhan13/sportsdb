import requests
import json
import time
from datetime import datetime

# FotMob's API Endpoint
# Using valid date format YYYYMMDD
today = datetime.now().strftime("%Y%m%d")
matches_url = f"https://www.fotmob.com/api/matches?date={today}&timezone=Asia/Kolkata&ccode3=IND"

def get_football_scores():
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    print(f"[*] Fetching FotMob: {matches_url}")
    try:
        response = requests.get(matches_url, headers=headers, timeout=10)
        print(f"[*] Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            total_matches = 0
            live_matches = 0
            
            # Loop through leagues
            for league in data.get('leagues', []):
                for match in league.get('matches', []):
                    total_matches += 1
                    
                    # Extract Data safely
                    home = match.get('home', {}).get('name')
                    away = match.get('away', {}).get('name')
                    status = match.get('status', {})
                    score = status.get('scoreStr', 'vs')
                    is_live = status.get('live', False)
                    started = status.get('started', False)
                    
                    if is_live:
                        live_matches += 1
                        print(f"⚽ [LIVE] {home} {score} {away}")
                    elif started:
                         print(f"⚽ [FINISHED/BREAK] {home} {score} {away}")
            
            print(f"[*] Total Matches: {total_matches} | Live: {live_matches}")
                    
        else:
            print(f"[FAIL] Error: {response.status_code}")
            print(response.text[:200])
            
    except Exception as e:
        print(f"[ERROR] Crash: {e}")

if __name__ == "__main__":
    get_football_scores()
